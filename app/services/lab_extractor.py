import re
from app.dictionaries.lab_test_aliases import LAB_TEST_ALIASES
class LabExtractor:
    def normalize(self,name:str)->str:
        low=name.lower().replace(' ','')
        for k,v in LAB_TEST_ALIASES.items():
            if k.lower().replace(' ','') in low: return v
        return name.strip()
    def extract(self,text:str)->list[dict]:
        rows=[]
        pat=re.compile(r'^(?P<name>[A-Za-z0-9 .()\-]+?)\s+(?P<val>[<>]?[0-9]+(?:\.[0-9]+)?)\s+(?P<unit>[A-Za-z0-9/^%µu.]+)?\s*(?P<ref>[0-9.]+\s*-\s*[0-9.]+)?',re.I)
        for line in text.splitlines():
            m=pat.search(line.strip())
            if m and any(ch.isalpha() for ch in m.group('name')):
                d=m.groupdict(); rows.append({'test_name_raw':d['name'].strip(),'test_name_standard':self.normalize(d['name']),'result_value':d['val'],'result_numeric':float(d['val'].lstrip('<>')),'unit':d.get('unit'),'reference_range':d.get('ref'),'raw_row_text':line,'confidence':0.75 if d.get('ref') and d.get('unit') else 0.55})
        return rows
