from __future__ import annotations
import re
from app.schemas.extraction_v2 import LabResultV2, ColumnStatuses

EXPECTED_UNITS={'HGB':['g/dL'],'HCT':['%'],'RBC':['10^6/uL','Mil/Cumm'],'WBC':['10^3/uL','1000/Cumm'],'PLT':['10^3/uL','1000/Cumm'],'MCV':['fL'],'MCH':['pg'],'MCHC':['g/dL'],'HbA1c':['%'],'FBS':['mg/dL'],'Creatinine':['mg/dL'],'HDL':['mg/dL'],'LDL':['mg/dL'],'Total Cholesterol':['mg/dL'],'Triglycerides':['mg/dL'],'AST':['U/L','IU/L'],'ALT':['U/L','IU/L'],'ALP':['U/L','IU/L'],'TSH':['uIU/mL','µIU/mL','mIU/L'],'PT':['Sec'],'PTT':['Sec'],'INR':['Ratio',''],'ESR':['mm/hr'],'Ferritin':['ng/mL'],'Vitamin D':['ng/mL']}
RANGES={'WBC':(0.1,200),'RBC':(.1,10),'HGB':(1,25),'HCT':(5,75),'MCV':(40,140),'MCH':(10,50),'MCHC':(20,45),'PLT':(1,2000),'HbA1c':(2,20),'FBS':(10,800),'Creatinine':(.1,25),'Ferritin':(1,5000),'Vitamin D':(1,300),'TSH':(.001,200),'HDL':(1,200),'LDL':(1,500),'Triglycerides':(1,3000),'BUN':(1,200),'Urea':(1,500),'AST':(1,5000),'ALT':(1,5000),'ESR':(0,200),'PT':(5,120),'INR':(.5,20),'PTT':(5,200),'CRP':(0,500),'DHT':(1,5000),'LH':(0,500),'FSH':(0,500),'Prolactin':(0,1000),'Testosterone':(0,3000),'Free Testosterone':(0,100),'Estradiol':(0,5000),'DHEA-SO4':(1,2000),'17OH-Progesterone':(0,100),'T3':(.1,1000),'T4':(.1,1000),'Free T3':(.1,50),'Free T4':(.1,20),'Calcium':(1,20),'Phosphorus':(1,20),'Iron':(1,1000),'TIBC':(1,1000),'Bilirubin Total':(0,50),'Bilirubin Direct':(0,50),'ALP':(1,5000),'Zinc':(1,1000),'Folic Acid':(.1,100),'Vitamin B12':(1,5000)}
QUAL_OK={'Color','Appearance','Protein','Urine Glucose','Ketone','Bilirubin Urine','Urobilinogen','Nitrite','Blood/Hb','Bacteria','Mucus','Casts','Crystals','Urine Culture','Epithelial Cells'}

def _normalize_unit(unit: str) -> str:
    return unit.strip().replace('µ','u').casefold()

def expected_unit_status(test_name: str, unit: str | None) -> str:
    expected = EXPECTED_UNITS.get(test_name)
    if not expected:
        return 'valid' if unit else 'missing_optional'
    if not unit:
        return 'missing_optional'
    normalized_unit = _normalize_unit(unit)
    return 'valid' if normalized_unit in {_normalize_unit(u) for u in expected} else 'invalid'

def compute_flag(value: float|None, ref: str|None) -> str|None:
    if value is None or not ref: return None
    s=ref.replace('≤','<=').replace('≥','>=')
    m=re.search(r'^\s*<\s*([\d.]+)', s)
    if m: return 'High' if value > float(m.group(1)) else None
    m=re.search(r'^\s*>\s*([\d.]+)', s)
    if m: return 'Low' if value < float(m.group(1)) else None
    m=re.search(r'([\d.]+)\s*-\s*([\d.]+)', s)
    if m:
        lo,hi=float(m.group(1)),float(m.group(2))
        return 'Low' if value < lo else 'High' if value > hi else None
    return None

class LabRowValidationService:
    def validate(self,row:LabResultV2, unsafe_ocr:bool=False)->LabResultV2:
        if unsafe_ocr:
            row.row_validation_status='unsafe_ocr_context'; row.row_save_allowed=False
            row.column_statuses=ColumnStatuses(test_name_status='unsafe_ocr_context',result_status='unsafe_ocr_context',unit_status='unsafe_ocr_context',reference_range_status='unsafe_ocr_context',source_flag_status='unsafe_ocr_context',computed_flag_status='unsafe_ocr_context',method_status='unsafe_ocr_context')
            return row
        row.column_statuses.test_name_status='valid' if row.test_name_standard else 'missing_required'
        row.column_statuses.result_status='valid' if row.result_value not in (None,'') else 'missing_required'
        row.column_statuses.unit_status=expected_unit_status(row.test_name_standard, row.unit)
        row.column_statuses.reference_range_status='valid' if row.reference_range else 'missing_optional'
        row.column_statuses.source_flag_status='valid' if row.source_flag else 'missing_optional'
        if row.source_flag in ('High','Low'):
            row.flag=row.source_flag; row.flag_source='source'
        else:
            row.source_flag=None; row.computed_flag=compute_flag(row.result_numeric,row.reference_range); row.flag=row.computed_flag; row.flag_source='computed' if row.computed_flag else None
        if row.result_numeric is None and row.test_name_standard not in QUAL_OK:
            row.row_validation_status='invalid'; row.reason_codes.append('qualitative_value_not_allowed')
        elif row.column_statuses.unit_status=='invalid':
            row.row_validation_status='invalid'; row.reason_codes.append('expected_unit_mismatch')
        elif row.result_numeric is not None and row.test_name_standard in RANGES and not (RANGES[row.test_name_standard][0] <= row.result_numeric <= RANGES[row.test_name_standard][1]):
            row.row_validation_status='review'; row.reason_codes.append('outside_physiological_range')
        else:
            row.row_validation_status='valid'
        row.row_save_allowed=row.row_validation_status=='valid' and row.column_statuses.result_status=='valid' and row.column_statuses.unit_status!='invalid'
        return row
