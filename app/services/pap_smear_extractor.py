import re
class PapSmearExtractor:
    def extract(self,text:str)->dict:
        def sec(name):
            m=re.search(name+r'[:\s]+(.+?)(?:\n[A-Z][A-Za-z /]+:|\Z)',text,re.I|re.S); return m.group(1).strip() if m else None
        return {'specimen_adequacy':sec('Specimen Adequacy'),'interpretation_result':sec('Interpretation|Result'),'full_narrative_report':text.strip() or None,'recommendation':sec('Recommendation'),'hpv_result':sec('HPV'),'doctor_or_pathologist_name':sec('Pathologist|Doctor'),'confidence':0.6}
