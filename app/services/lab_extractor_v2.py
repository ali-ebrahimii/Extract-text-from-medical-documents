from __future__ import annotations
import re
from app.schemas.extraction_v2 import LabResultV2
from app.services.lab_row_validation_service import LabRowValidationService

NUM_RE=r'\d+(?:\.\d+)?'
UNIT_RE=r'(?:%|10\^(?:3|6)\s*/\s*uL|fL|fl|pg|g/dL|g/dl|mg/dL|mg/dl|U/L|IU/L)'
REF_RE=rf'(?:<\s*{NUM_RE}|>\s*{NUM_RE}|{NUM_RE}\s*-\s*{NUM_RE}(?:\s*{UNIT_RE})?)'
FLAG_MAP={'H':'High','L':'Low','HIGH':'High','LOW':'Low'}

def _source_flag(text:str|None)->str|None:
    return FLAG_MAP.get((text or '').strip().upper())

def _match_test_name(line:str):
    clean=line.strip()
    for std, aliases in ALIASES.items():
        for alias in aliases:
            if re.fullmatch(rf'{re.escape(alias)}(?:\s*\([^)]*\))?', clean, re.I):
                return std, alias
    return None

ALIASES={'WBC':['WBC','W.B.C'],'RBC':['RBC','R.B.C'],'HGB':['HGB','Hb','Hemoglobin'],'HCT':['HCT','H.C.T'],'MCV':['MCV','M.C.V'],'MCH':['MCH','M.C.H'],'MCHC':['MCHC','M.C.H.C'],'RDW':['RDW'],'RDW-CV':['RDW-CV'],'RDW-SD':['RDW-SD'],'PLT':['PLT','Platelet','Platelets','Platelets count'],'PDW':['PDW'],'Neutrophils':['Neutrophils','Neut'],'Lymphocytes':['Lymphocytes','Lymph'],'Monocytes':['Monocytes'],'Eosinophils':['Eosinophils'],'Basophils':['Basophils'],'ESR':['ESR'],'FBS':['FBS','Glucose','Fasting blood sugar'], 'HbA1c':['HbA1c'], 'EAG':['EAG'],'BUN':['BUN'],'Urea':['Urea'],'Creatinine':['Creatinine','Cr'],'Uric Acid':['Uric Acid'],'Total Cholesterol':['Cholesterol','Total Cholesterol'],'Triglycerides':['Triglycerides','TG'],'HDL':['HDL'],'LDL':['LDL'],'AST':['AST','SGOT'],'ALT':['ALT','SGPT'],'ALP':['ALP'],'Calcium':['Calcium'],'Phosphorus':['Phosphorus'],'Iron':['Iron'],'TIBC':['TIBC'],'Bilirubin Total':['Bilirubin Total','Total Bilirubin'],'Bilirubin Direct':['Bilirubin Direct','Direct Bilirubin'],'TSH':['TSH'],'T3':['T3'],'T4':['T4'],'Free T3':['Free T3','FT3'],'Free T4':['Free T4','FT4'],'Vitamin D':['Vitamin D'],'Vitamin B12':['Vitamin B12','B12'],'Ferritin':['Ferritin'],'CRP':['CRP'],'LH':['LH'],'FSH':['FSH'],'Prolactin':['Prolactin'],'Testosterone':['Testosterone'],'Free Testosterone':['Free Testosterone'],'Estradiol':['Estradiol'],'DHEA-SO4':['DHEA-SO4','DHEAS'],'17OH-Progesterone':['17OH-Progesterone'],'DHT':['DHT'],'Zinc':['Zinc'],'Folic Acid':['Folic Acid'],'PT':['PT'],'PT Control':['PT Control'],'INR':['INR'],'PTT':['PTT'],'Specific Gravity':['Specific Gravity','SG'],'pH':['pH'],'Protein':['Protein'],'Urine Glucose':['Urine Glucose'],'Ketone':['Ketone'],'Nitrite':['Nitrite'],'Blood/Hb':['Blood','Hb urine'],'WBC/HPF':['WBC/HPF'],'RBC/HPF':['RBC/HPF'],'Bacteria':['Bacteria'],'Mucus':['Mucus'],'Casts':['Casts'],'Crystals':['Crystals'],'Color':['Color'],'Appearance':['Appearance'],'Epithelial Cells':['Epithelial']}
class LabExtractorV2:
    def __init__(self): self.validator=LabRowValidationService()
    def extract(self,text:str,lines:list[str]|None=None,unsafe_ocr:bool=False)->list[LabResultV2]:
        rows=[]; seen=set(); lines=lines or text.splitlines()
        culture=re.search(r'No\s+(?:bacteria\s+)?growth\s+after\s+(24|48)\s*(?:h|hr|hrs|hours)', text, re.I)
        if culture:
            rows.append(self.validator.validate(LabResultV2(test_name_standard='Urine Culture',test_name_raw='Culture',result_value=f'No growth after {culture.group(1)} hours',section='Culture',confidence=.9,source_text=culture.group(0),extraction_mode='culture_phrase'),unsafe_ocr))
        clean_lines=[line.strip() for line in lines if line.strip()]
        for i,line in enumerate(clean_lines):
            name=_match_test_name(line)
            if not name or (name[0], name[1].casefold()) in seen or i+3 >= len(clean_lines): continue
            val_line, unit_line, ref_line = clean_lines[i+1:i+4]
            if not (re.fullmatch(NUM_RE, val_line) and re.fullmatch(UNIT_RE, unit_line, re.I) and re.fullmatch(REF_RE, ref_line)): continue
            flag_line=clean_lines[i+4] if i+4 < len(clean_lines) else ''
            src=_source_flag(flag_line) if re.fullmatch(r'High|Low|H|L', flag_line, re.I) else None
            std, raw=name
            row=LabResultV2(test_name_standard=std,test_name_raw=raw,result_value=val_line,result_numeric=float(val_line),unit=unit_line,reference_range=ref_line,source_flag=src,section='Lab',confidence=.82,source_text=' | '.join(clean_lines[i:i+5 if src else i+4]),extraction_mode='vertical_tav')
            rows.append(self.validator.validate(row,unsafe_ocr)); seen.add((std, raw.casefold()))
        for line in lines:
            if re.search(r'No\s+(?:bacteria\s+)?growth\s+after', line, re.I): continue
            for std, aliases in ALIASES.items():
                if any(key[0] == std for key in seen): continue
                pat=r'\b('+'|'.join(re.escape(a) for a in aliases)+r')\b(?:\s*\([^)]*\))?\s*[:\-]?\s*(Negative|Positive|Trace|\d+(?:\.\d+)?)\s*('+UNIT_RE+r')?\s*('+REF_RE+r')?\s*(High|Low|H|L)?\b'
                m=re.search(pat,line,re.I)
                if not m: continue
                val=m.group(2); num=float(val) if re.fullmatch(NUM_RE,val) else None
                src=_source_flag(m.group(5))
                unit=(m.group(3) or '').strip() or None
                if unit and unit.upper()=='L': unit=None
                row=LabResultV2(test_name_standard=std,test_name_raw=m.group(1),result_value=val,result_numeric=num,unit=unit,reference_range=m.group(4),source_flag=src,section='Lab',confidence=.78,source_text=line)
                rows.append(self.validator.validate(row,unsafe_ocr)); seen.add((std, m.group(1).casefold())); break
        return rows
