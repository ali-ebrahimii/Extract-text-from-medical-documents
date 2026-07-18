from __future__ import annotations
import re
from app.schemas.extraction_v2 import LabResultV2
from app.services.lab_row_validation_service import LabRowValidationService
ALIASES={'WBC':['WBC'],'RBC':['RBC'],'HGB':['HGB','Hb'],'HCT':['HCT'],'MCV':['MCV'],'MCH':['MCH'],'MCHC':['MCHC'],'RDW':['RDW'],'PLT':['PLT','Platelet'],'Neutrophils':['Neutrophils','Neut'],'Lymphocytes':['Lymphocytes','Lymph'],'Monocytes':['Monocytes'],'Eosinophils':['Eosinophils'],'Basophils':['Basophils'],'ESR':['ESR'],'FBS':['FBS','Glucose'], 'HbA1c':['HbA1c'], 'EAG':['EAG'],'BUN':['BUN'],'Urea':['Urea'],'Creatinine':['Creatinine','Cr'],'Uric Acid':['Uric Acid'],'Total Cholesterol':['Cholesterol','Total Cholesterol'],'Triglycerides':['Triglycerides','TG'],'HDL':['HDL'],'LDL':['LDL'],'AST':['AST','SGOT'],'ALT':['ALT','SGPT'],'ALP':['ALP'],'Calcium':['Calcium'],'Phosphorus':['Phosphorus'],'Iron':['Iron'],'TIBC':['TIBC'],'Bilirubin Total':['Bilirubin Total','Total Bilirubin'],'Bilirubin Direct':['Bilirubin Direct','Direct Bilirubin'],'TSH':['TSH'],'T3':['T3'],'T4':['T4'],'Free T3':['Free T3','FT3'],'Free T4':['Free T4','FT4'],'Vitamin D':['Vitamin D'],'Vitamin B12':['Vitamin B12','B12'],'Ferritin':['Ferritin'],'CRP':['CRP'],'LH':['LH'],'FSH':['FSH'],'Prolactin':['Prolactin'],'Testosterone':['Testosterone'],'Free Testosterone':['Free Testosterone'],'Estradiol':['Estradiol'],'DHEA-SO4':['DHEA-SO4','DHEAS'],'17OH-Progesterone':['17OH-Progesterone'],'DHT':['DHT'],'Zinc':['Zinc'],'Folic Acid':['Folic Acid'],'PT':['PT'],'PT Control':['PT Control'],'INR':['INR'],'PTT':['PTT'],'Specific Gravity':['Specific Gravity','SG'],'pH':['pH'],'Protein':['Protein'],'Urine Glucose':['Urine Glucose'],'Ketone':['Ketone'],'Nitrite':['Nitrite'],'Blood/Hb':['Blood','Hb urine'],'WBC/HPF':['WBC/HPF'],'RBC/HPF':['RBC/HPF'],'Bacteria':['Bacteria'],'Mucus':['Mucus'],'Casts':['Casts'],'Crystals':['Crystals'],'Color':['Color'],'Appearance':['Appearance'],'Epithelial Cells':['Epithelial']}
class LabExtractorV2:
    def __init__(self): self.validator=LabRowValidationService()
    def extract(self,text:str,lines:list[str]|None=None,unsafe_ocr:bool=False)->list[LabResultV2]:
        rows=[]; seen=set(); lines=lines or text.splitlines()
        culture=re.search(r'No\s+(?:bacteria\s+)?growth\s+after\s+(24|48)\s*(?:h|hr|hrs|hours)', text, re.I)
        if culture:
            rows.append(self.validator.validate(LabResultV2(test_name_standard='Urine Culture',test_name_raw='Culture',result_value=f'No growth after {culture.group(1)} hours',section='Culture',confidence=.9,source_text=culture.group(0),extraction_mode='culture_phrase'),unsafe_ocr))
        for line in lines:
            if re.search(r'No\s+(?:bacteria\s+)?growth\s+after', line, re.I): continue
            for std, aliases in ALIASES.items():
                if std in seen: continue
                pat=r'\b('+'|'.join(re.escape(a) for a in aliases)+r')\b\s*[:\-]?\s*(Negative|Positive|Trace|\d+(?:\.\d+)?)\s*([^\s<>\d]{0,8}(?:/[A-Za-z]+)?)?\s*(<\s*\d+(?:\.\d+)?|>\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)?\s*(High|Low|H|L)?\b'
                m=re.search(pat,line,re.I)
                if not m: continue
                val=m.group(2); num=float(val) if re.fullmatch(r'\d+(?:\.\d+)?',val) else None
                src={'H':'High','L':'Low','High':'High','Low':'Low'}.get((m.group(5) or '').title() or (m.group(5) or '').upper())
                unit=(m.group(3) or '').strip() or None
                if unit and unit.upper()=='L': unit=None
                row=LabResultV2(test_name_standard=std,test_name_raw=m.group(1),result_value=val,result_numeric=num,unit=unit,reference_range=m.group(4),source_flag=src,section='Lab',confidence=.78,source_text=line)
                rows.append(self.validator.validate(row,unsafe_ocr)); seen.add(std); break
        return rows
