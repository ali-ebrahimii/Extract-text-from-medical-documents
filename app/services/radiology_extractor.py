import re
class RadiologyExtractor:
    def extract(self,text:str)->dict:
        def sec(name):
            m=re.search(name+r'[:\s]+(.+?)(?:\n[A-Z][A-Za-z /]+:|\Z)',text,re.I|re.S); return m.group(1).strip() if m else None
        modality=next((m for m in ['MRI','CT','Ultrasound','X-ray'] if m.lower() in text.lower()), None)
        return {'imaging_modality':modality,'body_part_or_exam_name':sec('Exam|Study'),'findings':sec('Findings'),'impression_conclusion':sec('Impression|Conclusion'),'full_narrative_report':text.strip() or None,'radiologist_name':sec('Radiologist'),'confidence':0.6}
