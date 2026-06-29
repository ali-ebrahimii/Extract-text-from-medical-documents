import hashlib, re
from app.core.config import settings

def hash_national_id(national_id: str) -> str:
    return hashlib.sha256(national_id.encode("utf-8")).hexdigest()

class CommonFieldExtractor:
    def _field(self, value, confidence=.85, **extra):
        d={"value": value, "confidence": confidence if value is not None else 0.0}; d.update(extra); return d
    def extract_structured(self, text: str) -> dict:
        t=text or ""
        def search(pattern, flags=re.I):
            m=re.search(pattern,t,flags); return m.group(1).strip() if m else None
        nid=search(r"(?:National\s*ID|کد\s*(?:ملی|ملي)|كد\s*ملي)\s*[:：]?\s*([0-9]{10})") or search(r"\b([0-9]{10})\b")
        date=search(r"(?:تاریخ\s*(?:پذیرش|گزارش)|تاريخ\s*(?:پذيرش|گزارش)|Report\s*Date|Date)\s*[:：]?\s*(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})") or search(r"(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")
        name=search(r"(?:Patient\s*Name|نام\s*(?:بیمار|بيمار)|Name)\s*[:：]?\s*([^\n]+)")
        sex=None; age=None
        m=re.search(r"\b(آقای|آقاي|خانم)\s+([^\n]+?)\s+سن\s*[:：]?\s*([0-9]{1,3})",t)
        if m:
            sex="female" if m.group(1)=="خانم" else "male"; name=name or m.group(2).strip(" -"); age=int(m.group(3))
        if sex is None:
            if re.search(r"\b(Male|آقای|آقاي)\b",t,re.I): sex="male"
            elif re.search(r"\b(Female|خانم)\b",t,re.I): sex="female"
        if age is None:
            a=search(r"(?:Age|سن)\s*[:：]?\s*([0-9]{1,3})(?:\s*سال)?")
            age=int(a) if a else None
        cal="jalali" if date and date.startswith("14") else ("gregorian" if date else None)
        raw_allowed=getattr(settings,"allow_raw_national_id",False)
        return {
            "patient_name": self._field(name),
            "national_id": {"value": nid if raw_allowed else None, "hash": hash_national_id(nid) if nid else None, "confidence": .9 if nid else 0.0},
            "date_of_test_or_report": self._field(date,.9, calendar=cal),
            "test_or_report_name": self._field(search(r"(?:Test|Report|Exam)\s*[:：]?\s*([^\n]+)")),
            "center_name": self._field(search(r"(?:Center|Laboratory|Hospital|Clinic|آزمایشگاه|آزمايشگاه|بیمارستان|بيمارستان|کلینیک)\s*[:：]?\s*([^\n]+)")),
            "doctor_name": self._field(search(r"(?:Doctor|Physician|پزشک|پزشك)\s*[:：]?\s*([^\n]+)")),
            "age": self._field(age,.85), "sex": self._field(sex,.85),
            "tracking_number": self._field(search(r"(?:Tracking|پیگیری|پذیرش)\s*(?:No|Number|شماره)?\s*[:：]?\s*([A-Za-z0-9_-]+)")),
        }
    def extract(self,text:str)->dict:
        s=self.extract_structured(text)
        return {k: (v.get("value") if isinstance(v,dict) else v) for k,v in s.items()} | {"national_id_hash": s["national_id"].get("hash")}
