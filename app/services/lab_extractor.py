import re
from app.dictionaries.lab_test_aliases import LAB_TEST_ALIASES

METHODS={"Photometr","ELISA","ECL","HPLC","Immunoassay"}
FLAGS={"High","Low","Critical","H","L"}
class LabExtractor:
    def normalize(self,name:str)->str:
        key=re.sub(r"\s+"," ",name.strip())
        compact=key.lower().replace(" ","")
        for k,v in LAB_TEST_ALIASES.items():
            if compact == k.lower().replace(" ","") or compact.startswith(k.lower().replace(" ","")):
                return v
        return key
    def _confidence(self,d):
        score=.35
        if d.get('test_name_standard'): score+=.2
        if d.get('result_value'): score+=.2
        if d.get('unit'): score+=.1
        if d.get('reference_range'): score+=.1
        if d.get('method'): score+=.05
        return min(score, .95)
    def extract(self,text:str)->list[dict]:
        rows=[]
        for page_no, page_text in enumerate((text or "").split("\f"), start=1):
            for raw in page_text.splitlines():
                line=" ".join(raw.strip().split())
                if not line or not re.search(r"[A-Za-z]",line): continue
                m=re.match(r"^(?P<name>[A-Za-z0-9 .()\-/]+?)\s+(?P<val>[*]?[<>]?[0-9]+(?:\.\d+)?)\s+(?P<rest>.+)$", line)
                if not m: continue
                name=m.group('name').strip(); val=m.group('val'); rest=m.group('rest')
                tokens=rest.split(); flag=None
                if tokens and tokens[-1] in FLAGS: flag=tokens.pop()
                ref=None
                rest2=" ".join(tokens)
                ref_match=re.search(r"(Up to\s*[0-9.]+|[<>]\s*[0-9.]+|[0-9.]+\s*-\s*[0-9.]+\s*%?)\s*$", rest2, re.I)
                if ref_match:
                    ref=ref_match.group(1).strip(); before=rest2[:ref_match.start()].strip()
                else: before=rest2
                method=None
                bt=before.split()
                if bt and bt[-1] in METHODS:
                    method=bt[-1]; unit=" ".join(bt[:-1]).strip() or None
                else: unit=before.strip() or None
                numeric=float(re.sub(r"^[*<>]+","",val))
                d={"category":None,"test_name_raw":name,"test_name_standard":self.normalize(name),"result_value":val.lstrip('*'),"result_numeric":numeric,"unit":unit,"reference_range":ref,"abnormal_flag":flag,"method":method,"sample_type":None,"page_number":page_no,"raw_row_text":raw,"confidence":0.0}
                d["confidence"]=self._confidence(d); rows.append(d)
        return rows
