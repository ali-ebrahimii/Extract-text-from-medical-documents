from __future__ import annotations
import re
from app.schemas.extraction_v2 import CommonFieldV2, NationalIdField
from app.services.privacy_service import normalize_persian_text, validate_iranian_national_id, mask_national_id, hash_sha256

BAD_TRACK = {'Result','Hormone','Biochemistry','Hematology','Urine','Culture','Method','Reference'}
DOCTOR_LABELS = ['نام پزشک','پزشک معالج','درخواست کننده','Doctor','Physician','Lab.Director','دکتر مسئول']

def valid_tracking_number(value: str | None, labelled: bool=True) -> bool:
    if not value or any(b.lower() == value.lower() for b in BAD_TRACK): return False
    if re.search(r'(?:Result|Hormone|Culture|Method|Reference|تاریخ|سن|دکتر)', value, re.I): return False
    if re.fullmatch(r'1[34]\d{2}', value): return False
    if re.fullmatch(r'1[34]\d{2}[/-]\d{1,2}[/-]\d{1,2}', value): return False
    if not labelled: return False
    return bool(re.fullmatch(r'[A-Z]-\d{4,6}-\d{3,5}', value))

class CommonFieldValidationService:
    def extract(self, text: str, unsafe_ocr: bool=False, privacy_mode: str='internal') -> dict:
        text = normalize_persian_text(text); fields: dict = {}
        if unsafe_ocr:
            for k in ['center_name','tracking_number','date_of_test_or_report','patient_name','sex','age','doctor_name']:
                fields[k]=CommonFieldV2(field_validation_status='unsafe_ocr_context').model_dump(exclude_none=True)
            fields['national_id']=NationalIdField(field_validation_status='unsafe_ocr_context').model_dump(exclude_none=True)
            return fields
        nid = self._national_id(text, privacy_mode); fields['national_id']=nid.model_dump()
        fields['tracking_number']=self._tracking(text).model_dump(exclude_none=True)
        fields['date_of_test_or_report']=self._date(text).model_dump(exclude_none=True)
        fields['patient_name']=self._patient(text).model_dump(exclude_none=True)
        fields['sex']=self._sex(text).model_dump(exclude_none=True)
        fields['age']=self._age(text).model_dump(exclude_none=True)
        fields['doctor_name']=self._doctor(text).model_dump(exclude_none=True)
        fields['center_name']=self._center(text).model_dump(exclude_none=True)
        return fields
    def _national_id(self,text,privacy_mode):
        m=re.search(r'(کد ملی|National\s*(?:ID|Code))\s*[:：]?\s*(\d{10})', text, re.I)
        if not m: return NationalIdField(field_validation_status='missing_required')
        raw=m.group(2); ok=validate_iranian_national_id(raw); masked=mask_national_id(raw)
        return NationalIdField(raw_value=None if privacy_mode=='safe_share' else raw, masked_value=masked, hash_sha256=hash_sha256(raw), checksum_valid=ok, extraction_method='explicit_label', confidence=.95 if ok else .65, source_text_masked=f'{m.group(1)} : {masked}', field_validation_status='valid' if ok else 'review', field_backend_usable=ok)
    def _tracking(self,text):
        m=re.search(r'(?:شماره\s*(?:پذیرش|پیگیری|جواب)?|Tracking|Admission)\s*[:：]?\s*([A-Z]-\d{4,6}-\d{3,5})', text, re.I)
        labelled=bool(m)
        if not m:
            m=re.search(r'\b([A-Z]-\d{4,6}-\d{3,5})\b', text[:500], re.I)
        val=m.group(1) if m else None; ok=valid_tracking_number(val, labelled or bool(m))
        return CommonFieldV2(value=val, confidence=.9 if ok else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if ok else 'missing_optional', field_backend_usable=ok)
    def _date(self,text):
        m=re.search(r'(?:تاریخ\s*(?:پذیرش|جوابدهی|جواب)?|Date|Report Date|Admission Date)\s*[:：]?\s*(1[34]\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01]))', text, re.I)
        return CommonFieldV2(value=m.group(1) if m else None, confidence=.85 if m else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if m else 'missing_required', field_backend_usable=bool(m))
    def _compact_tav_patient_line(self,text):
        m=re.search(r'(?m)^\s*([^\n\r:-]{2,40})-\s*(آقای|خانم)\s+([^\n\r:-]{2,30})-\s*دکتر\s*(\d{1,3})\s*[:：]\s*سن', text)
        if not m: return None
        age=int(m.group(4))
        if not 0 <= age <= 120: return None
        return {
            'family': normalize_persian_text(m.group(1).strip()),
            'title': m.group(2),
            'given': normalize_persian_text(m.group(3).strip()),
            'age': age,
            'source': m.group(0),
        }
    def _patient(self,text):
        compact=self._compact_tav_patient_line(text)
        if compact:
            return CommonFieldV2(value=f"{compact['given']} {compact['family']}", confidence=.85, source_text=compact['source'], field_validation_status='valid', field_backend_usable=True)
        m=re.search(r'(?:نام\s*(?:بیمار)?|Patient(?: Name)?)\s*[:：]?\s*([^\n\r:]{2,40})', text, re.I)
        val=normalize_persian_text(m.group(1)) if m else None
        return CommonFieldV2(value=val, confidence=.8 if val else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if val else 'missing_required', field_backend_usable=bool(val))
    def _sex(self,text):
        compact=self._compact_tav_patient_line(text)
        if compact:
            return CommonFieldV2(value='male' if compact['title']=='آقای' else 'female', confidence=.85, source_text=compact['source'], field_validation_status='valid', field_backend_usable=True)
        m=re.search(r'(?:جنسیت|Sex)\s*[:：]?\s*(زن|مرد|Female|Male|F|M)\b', text, re.I)
        return CommonFieldV2(value=m.group(1) if m else None, confidence=.75 if m else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if m else 'missing_optional', field_backend_usable=bool(m))
    def _age(self,text):
        compact=self._compact_tav_patient_line(text)
        if compact:
            return CommonFieldV2(value=compact['age'], confidence=.85, source_text=compact['source'], field_validation_status='valid', field_backend_usable=True)
        m=re.search(r'(?:سن|Age)\s*[:：]?\s*(\d{1,3})\s*(?:سال|Y|Years?)?', text, re.I)
        age=int(m.group(1)) if m and 0 <= int(m.group(1)) <= 120 else None
        return CommonFieldV2(value=age, confidence=.8 if age is not None else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if age is not None else 'missing_optional', field_backend_usable=age is not None)
    def _doctor(self,text):
        for label in DOCTOR_LABELS:
            m=re.search(re.escape(label)+r'\s*[:：]?\s*([^\n\r:]{2,40})', text, re.I)
            if m and not re.search(r'(?:سن|Age)|\d{2,}', m.group(0)):
                return CommonFieldV2(value=normalize_persian_text(m.group(1)), confidence=.8, source_text=m.group(0), field_validation_status='valid', field_backend_usable=True)
        return CommonFieldV2(field_validation_status='missing_optional')
    def _center(self,text):
        m=re.search(r'(آزمایشگاه[^\n\r]{2,50}|Laboratory[^\n\r]{2,50})', text, re.I)
        return CommonFieldV2(value=normalize_persian_text(m.group(1)) if m else None, confidence=.7 if m else 0, source_text=m.group(0) if m else None, field_validation_status='valid' if m else 'missing_optional', field_backend_usable=bool(m))
