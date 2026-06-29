import re
from app.dictionaries.lab_test_aliases import LAB_TEST_ALIASES
from app.services.relevance_service import normalize_digits

METHODS={"Photometr","ELISA","ECL","HPLC","Immunoassay"}
FLAGS={"High","Low","Critical","H","L"}
GUIDELINE_LABELS={"high","low","h","l","critical","desirable","borderline","borderline high","borderline hight","near optimal","optimal","average risk","low risk","high risk","risk","normal","abnormal","negative","positive","comment","interpretation"}
_SKIP_LABEL_RE=re.compile(r"^\s*(patient|name|doctor|physician|address|tel|phone|mobile|fax|age|sex|gender|printed|print\s+on|report\s+date|date\s+of|reference\s+range|normal\s+range|specimen|collected|received|lab\s+no|sample\s+no|page|test|result|unit|flag|method|biochemistry|hematology|نام|پزشک|پزشك|آدرس|تلفن)\b",re.I)
_REF_RE=re.compile(r"(Up to\s*[0-9.]+|[<>]\s*[0-9.]+|[0-9.]+\s*-\s*[0-9.]+)(\s*[A-Za-z%/µ]+)?\s*$",re.I)
_LINE_RE=re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9 .()\-/]*?)\s+(?P<val>[*]?[<>]?[0-9]+(?:\.\d+)?)\s+(?P<rest>.+)$")
_DATE_RE=re.compile(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b|\d{1,2}:\d{2}:\d{2}")
_NUM_RE=re.compile(r"^[*]?[<>]?\d+(?:\.\d+)?$")
_UNIT_RE=re.compile(r"^(mg/dL|g/dL|U/L|IU/L|µIU/mL|uIU/mL|ng/mL|10\^3\s*/?uL|10\^6\s*/?uL|%|fL|pg)$",re.I)

class LabExtractor:
    def normalize(self,name:str)->str:
        key=re.sub(r"\s+"," ",name.strip()); compact=key.lower().replace(" ","")
        for k,v in LAB_TEST_ALIASES.items():
            if compact == k.lower().replace(" ","") or compact.startswith(k.lower().replace(" ","")): return v
        return key
    def _is_known(self,name:str)->bool:
        compact=re.sub(r"\s+","",name.strip().lower())
        return any(compact==k.lower().replace(" ","") or compact.startswith(k.lower().replace(" ","")) for k in LAB_TEST_ALIASES)
    def _is_guideline_name(self,name:str)->bool:
        n=re.sub(r"\s+"," ",re.sub(r"[^A-Za-z ]"," ",name).strip()).lower()
        return n in GUIDELINE_LABELS
    def _is_reference_comment(self,line:str)->bool:
        parts=re.split(r"[:<>\d]",line,1); label=parts[0].strip()
        return bool(label and self._is_guideline_name(label) and re.search(r"[<>:]|\d+\s*-\s*\d+",line))
    def _is_skippable(self,line:str)->bool:
        return bool(_SKIP_LABEL_RE.match(line) or _DATE_RE.search(line) or self._is_reference_comment(line))
    def _confidence(self,d)->float:
        score=.35
        if d.get('test_name_standard') and d['test_name_standard']!=d.get('test_name_raw'): score+=.2
        if d.get('result_numeric') is not None: score+=.2
        if d.get('unit'): score+=.1
        if d.get('reference_range'): score+=.1
        if d.get('method'): score+=.05
        if not d.get('unit') and not d.get('reference_range'): score-=.2
        return max(.1,min(score,.95))
    def _row(self,name,val,rest,raw,page_no):
        tokens=rest.split(); flag=None
        if tokens and tokens[-1] in FLAGS: flag=tokens.pop()
        rest2=" ".join(tokens); ref=None; m=_REF_RE.search(rest2)
        before=rest2
        if m: ref=" ".join(m.group(0).split()).strip(); before=rest2[:m.start()].strip()
        method=None; bt=before.split()
        if bt and bt[-1] in METHODS: method=bt[-1]; unit=" ".join(bt[:-1]).strip() or None
        else: unit=before.strip() or None
        if self._is_guideline_name(name) or not (ref or unit or method or self._is_known(name)): return None
        try: numeric=float(re.sub(r"^[*<>]+","",val))
        except ValueError: numeric=None
        d={"category":None,"test_name_raw":name,"test_name_standard":self.normalize(name),"result_value":val.lstrip('*'),"result_numeric":numeric,"unit":unit,"reference_range":ref,"abnormal_flag":flag,"method":method,"sample_type":None,"page_number":page_no,"raw_row_text":raw,"confidence":0.0}
        d['confidence']=self._confidence(d); return d
    def extract_column_major_blocks(self,text:str)->list[dict]:
        rows=[]; text=normalize_digits(text or "")
        for page_no,page_text in enumerate(text.split('\f'),1):
            lines=[" ".join(l.strip().split()) for l in page_text.splitlines() if l.strip()]
            header_hits=sum(1 for h in ("Test","Result","Unit","Normal Range","Method","Flag","Biochemistry","Hematology") if any(h.lower() in l.lower() for l in lines[:25]))
            if header_hits<3: continue
            i=0
            while i<len(lines):
                name=lines[i]
                if not self._is_known(name): i+=1; continue
                j=i+1
                if j>=len(lines) or not _NUM_RE.match(lines[j]): i+=1; continue
                val=lines[j]; j+=1; unit=None; refs=[]; flag=None; method=None
                if j<len(lines) and _UNIT_RE.match(lines[j]): unit=lines[j]; j+=1
                while j<len(lines) and not self._is_known(lines[j]):
                    cur=lines[j]
                    if cur in METHODS: method=cur; j+=1; break
                    if cur in FLAGS and flag is None and len(refs)<=1: flag=cur
                    elif not _SKIP_LABEL_RE.match(cur): refs.append(cur)
                    j+=1
                raw=" | ".join(lines[i:j]);
                try: numeric=float(re.sub(r"^[*<>]+","",val))
                except ValueError: numeric=None
                d={"category":None,"test_name_raw":name,"test_name_standard":self.normalize(name),"result_value":val.lstrip('*'),"result_numeric":numeric,"unit":unit,"reference_range":"; ".join(refs) or None,"abnormal_flag":flag,"method":method,"sample_type":None,"page_number":page_no,"raw_row_text":raw,"confidence":0.0}
                d['confidence']=self._confidence(d); rows.append(d); i=j
        return rows
    def extract(self,text:str)->list[dict]:
        rows=[]; text=normalize_digits(text or "")
        for page_no,page_text in enumerate(text.split('\f'),1):
            for raw in page_text.splitlines():
                line=" ".join(raw.strip().split())
                if not line or not re.search(r"[A-Za-z]",line) or self._is_skippable(line): continue
                m=_LINE_RE.match(line)
                if not m: continue
                d=self._row(m.group('name').strip(),m.group('val'),m.group('rest'),raw,page_no)
                if d: rows.append(d)
        rows.extend(self.extract_column_major_blocks(text))
        dedup={}
        for r in rows: dedup[(r.get('page_number'),r.get('test_name_standard'),r.get('result_value'))]=r
        return list(dedup.values())
