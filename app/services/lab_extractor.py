import re
from app.dictionaries.lab_test_aliases import LAB_TEST_ALIASES

METHODS={"Photometr","ELISA","ECL","HPLC","Immunoassay"}
FLAGS={"High","Low","Critical","H","L"}

# Field-label / metadata lines (matched at the start of a line, word-bounded)
# that must not be parsed as lab result rows.
_SKIP_LABEL_RE=re.compile(
    r"^\s*(patient|name|doctor|physician|address|tel|phone|mobile|fax|"
    r"age|sex|gender|printed|print\s+on|report\s+date|date\s+of|"
    r"reference\s+range|normal\s+range|specimen|collected|received|"
    r"lab\s+no|sample\s+no|page|نام|پزشک|پزشك|آدرس|تلفن)\b",
    re.I,
)
# Reference range: <37 / < 40 / >x / 0.4 - 5.0 / 38.8-50 / Up to 5
# with an optional trailing repeated unit (e.g. "38.8-50 %", "81.2-95.1 fl").
_REF_RE=re.compile(
    r"(Up to\s*[0-9.]+|[<>]\s*[0-9.]+|[0-9.]+\s*-\s*[0-9.]+)(\s*[A-Za-z%/µ]+)?\s*$",
    re.I,
)
_LINE_RE=re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9 .()\-/]*?)\s+(?P<val>[*]?[<>]?[0-9]+(?:\.\d+)?)\s+(?P<rest>.+)$")
_DATE_RE=re.compile(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b|\d{1,2}:\d{2}:\d{2}")


class LabExtractor:
    def normalize(self,name:str)->str:
        key=re.sub(r"\s+"," ",name.strip())
        compact=key.lower().replace(" ","")
        for k,v in LAB_TEST_ALIASES.items():
            if compact == k.lower().replace(" ","") or compact.startswith(k.lower().replace(" ","")):
                return v
        return key

    def _is_known(self,name:str)->bool:
        compact=re.sub(r"\s+","",name.strip().lower())
        return any(compact.startswith(k.lower().replace(" ","")) for k in LAB_TEST_ALIASES)

    def _is_skippable(self,line:str)->bool:
        if _SKIP_LABEL_RE.match(line): return True
        if _DATE_RE.search(line): return True
        return False

    def _confidence(self,d)->float:
        score=.35
        if d.get('test_name_standard') and d['test_name_standard']!=d.get('test_name_raw'): score+=.2
        if d.get('result_numeric') is not None: score+=.2
        if d.get('unit'): score+=.1
        if d.get('reference_range'): score+=.1
        if d.get('method'): score+=.05
        # Penalize rows with neither a unit nor a reference range (less reliable).
        if not d.get('unit') and not d.get('reference_range'): score-=.2
        return max(.1, min(score, .95))

    def extract(self,text:str)->list[dict]:
        rows=[]
        for page_no, page_text in enumerate((text or "").split("\f"), start=1):
            for raw in page_text.splitlines():
                line=" ".join(raw.strip().split())
                if not line or not re.search(r"[A-Za-z]",line): continue
                if self._is_skippable(line): continue
                m=_LINE_RE.match(line)
                if not m: continue
                name=m.group('name').strip(); val=m.group('val'); rest=m.group('rest')
                tokens=rest.split(); flag=None
                if tokens and tokens[-1] in FLAGS: flag=tokens.pop()
                rest2=" ".join(tokens)
                ref=None
                ref_match=_REF_RE.search(rest2)
                if ref_match:
                    ref=" ".join(ref_match.group(0).split()).strip(); before=rest2[:ref_match.start()].strip()
                else:
                    before=rest2
                method=None
                bt=before.split()
                if bt and bt[-1] in METHODS:
                    method=bt[-1]; unit=" ".join(bt[:-1]).strip() or None
                else:
                    unit=before.strip() or None
                standard=self.normalize(name)
                # Conservative guard: require at least a reference range, a unit,
                # a known method, or a recognized test name. Otherwise skip the
                # line to avoid parsing stray text as a lab result.
                if not (ref or unit or method or self._is_known(name)):
                    continue
                numeric=None
                try:
                    numeric=float(re.sub(r"^[*<>]+","",val))
                except ValueError:
                    numeric=None
                d={"category":None,"test_name_raw":name,"test_name_standard":standard,"result_value":val.lstrip('*'),"result_numeric":numeric,"unit":unit,"reference_range":ref,"abnormal_flag":flag,"method":method,"sample_type":None,"page_number":page_no,"raw_row_text":raw,"confidence":0.0}
                d["confidence"]=self._confidence(d); rows.append(d)
        return rows
