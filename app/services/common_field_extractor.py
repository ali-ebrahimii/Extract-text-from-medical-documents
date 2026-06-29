import hashlib, re
from app.core.config import settings
from app.services.relevance_service import normalize_persian

def hash_national_id(national_id: str) -> str:
    return hashlib.sha256(national_id.encode("utf-8")).hexdigest()

# Tokens that mark a line as a lab table header rather than a real center name.
_HEADER_TOKENS = ("result", "unit", "reference", "range", "method", "normal", "cbc", "wbc", "rbc", "test name")
# Keywords that indicate a center/lab/hospital name at the top of a page.
_CENTER_KEYWORDS = ("laboratory", "lab", "pathobiology", "hospital", "clinic", "center", "centre",
                    "آزمایشگاه", "آزمايشگاه", "بیمارستان", "بيمارستان", "درمانگاه", "کلینیک", "کلينيک", "پاتوبیولوژی", "پاتوبيولوژي")


class CommonFieldExtractor:
    def _field(self, value, confidence=.85, **extra):
        d={"value": value, "confidence": confidence if value is not None else 0.0}; d.update(extra); return d

    def _looks_like_header(self, line: str) -> bool:
        low=line.lower()
        return sum(tok in low for tok in _HEADER_TOKENS) >= 2

    def _center_name(self, text: str) -> tuple[str | None, float]:
        """Resolve center/lab name with source priority.

        1. explicit label (e.g. "Center: X", "مرکز: X")
        2. known top-of-page center pattern (first lines starting with a center keyword)
        Candidates that look like table headers are rejected.
        """
        # 1. explicit label
        m=re.search(r"(?:Center|Centre|مرکز)\s*[:：]\s*([^\n]+)", text, re.I)
        if m:
            cand=self._clean(m.group(1))
            if cand and not self._looks_like_header(cand):
                return cand[:120], .9
        # 2. top-of-page center pattern: scan the first non-empty lines
        for raw in [l for l in text.splitlines() if l.strip()][:6]:
            line=" ".join(raw.split())
            low=line.lower()
            if self._looks_like_header(line):
                continue
            if any(kw in low for kw in _CENTER_KEYWORDS):
                return self._clean(line)[:120], .7
        return None, 0.0

    @staticmethod
    def _clean(value: str) -> str:
        # Strip surrounding noise punctuation (e.g. leading/trailing '#', '*').
        return re.sub(r"^[\s#*:|/\\.-]+|[\s#*:|/\\.-]+$", "", value).strip()

    def _tracking_number(self, text: str) -> str | None:
        # explicit label first
        m=re.search(r"(?:Tracking|Report\s*No|پیگیری|پذیرش)\s*(?:No|Number|شماره)?\s*[:：]\s*([A-Za-z0-9_-]+)", text, re.I)
        if m:
            return m.group(1).strip()
        # known pattern like O-40412-1721
        m=re.search(r"\b([A-Za-z]-?\d{3,}-\d{3,})\b", text)
        if m:
            return m.group(1).strip()
        return None

    def extract_structured(self, text: str) -> dict:
        # Normalize Persian/Arabic variants and presentation-form glyphs so
        # labels and center names from real PDF text layers match reliably.
        t=normalize_persian(text or "")
        def search(pattern, flags=re.I):
            m=re.search(pattern,t,flags); return m.group(1).strip() if m else None
        nid=search(r"(?:National\s*ID|کد\s*(?:ملی|ملي)|كد\s*ملي)\s*[:：]?\s*([0-9]{10})") or search(r"\b([0-9]{10})\b")
        # Main report date: prefer explicitly labelled dates (پذیرش/گزارش/Report Date/Date of test).
        date=search(r"(?:تاریخ\s*(?:پذیرش|گزارش)|تاريخ\s*(?:پذيرش|گزارش)|Report\s*Date|Date\s*of\s*test|Date)\s*[:：]?\s*(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})") or search(r"(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")
        # Print date (kept separate from the main report date).
        print_date=search(r"(?:Print(?:ed)?(?:\s*On)?|تاریخ\s*چاپ|تاريخ\s*چاپ)\s*[:：]?\s*(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")
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
        center_value, center_conf=self._center_name(t)
        tracking=self._tracking_number(t)
        return {
            "patient_name": self._field(name),
            "national_id": {"value": nid if raw_allowed else None, "hash": hash_national_id(nid) if nid else None, "confidence": .9 if nid else 0.0},
            "date_of_test_or_report": self._field(date,.9, calendar=cal),
            "print_date": self._field(print_date,.8),
            "test_or_report_name": self._field(search(r"(?:Test|Report|Exam)\s*[:：]\s*([^\n]+)")),
            "center_name": self._field(center_value, center_conf),
            "doctor_name": self._field(search(r"(?:Doctor|Physician|پزشک|پزشك)\s*[:：]?\s*([^\n]+)")),
            "age": self._field(age,.85), "sex": self._field(sex,.85),
            "tracking_number": self._field(tracking),
        }

    def extract(self,text:str)->dict:
        s=self.extract_structured(text)
        return {k: (v.get("value") if isinstance(v,dict) else v) for k,v in s.items()} | {"national_id_hash": s["national_id"].get("hash")}
