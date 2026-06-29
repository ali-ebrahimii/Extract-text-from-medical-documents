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
    def _field(self, value, confidence=.85, source_text=None, source_line_index=None, **extra):
        d={"value": value, "confidence": confidence if value is not None else 0.0,
           "source_text": source_text if value is not None else None,
           "source_line_index": source_line_index if value is not None else None}
        d.update(extra); return d

    def _looks_like_header(self, line: str) -> bool:
        low=line.lower()
        return sum(tok in low for tok in _HEADER_TOKENS) >= 2

    @staticmethod
    def _clean(value: str) -> str:
        # Strip surrounding noise punctuation (e.g. leading/trailing '#', '*').
        return re.sub(r"^[\s#*:|/\\.-]+|[\s#*:|/\\.-]+$", "", value).strip()

    def _search_lines(self, lines: list[str], pattern: str, flags=re.I, group: int = 1):
        """Return (value, line_index, source_text) for the first matching line."""
        rx=re.compile(pattern, flags)
        for i, line in enumerate(lines):
            m=rx.search(line)
            if m:
                return m.group(group).strip(), i, line.strip()
        return None, None, None

    def _center_name(self, lines: list[str]) -> tuple[str | None, float, int | None, str | None]:
        """Resolve center/lab name with source priority.

        1. explicit label (e.g. "Center: X", "مرکز: X")
        2. known top-of-page center pattern (first lines starting with a center keyword)
        Candidates that look like table headers are rejected.
        """
        # 1. explicit label
        for i, line in enumerate(lines):
            m=re.search(r"(?:Center|Centre|مرکز)\s*[:：]\s*([^\n]+)", line, re.I)
            if m:
                cand=self._clean(m.group(1))
                if cand and not self._looks_like_header(cand):
                    return cand[:120], .9, i, line.strip()
        # 2. top-of-page center pattern: scan the first non-empty lines
        seen=0
        for i, raw in enumerate(lines):
            if not raw.strip():
                continue
            seen+=1
            if seen>6:
                break
            line=" ".join(raw.split())
            low=line.lower()
            if self._looks_like_header(line):
                continue
            if any(kw in low for kw in _CENTER_KEYWORDS):
                return self._clean(line)[:120], .7, i, line.strip()
        return None, 0.0, None, None

    def _tracking_number(self, lines: list[str]) -> tuple[str | None, int | None, str | None]:
        # explicit label first
        v, idx, src=self._search_lines(lines, r"(?:Tracking|Report\s*No|پیگیری|پذیرش)\s*(?:No|Number|شماره)?\s*[:：]\s*([A-Za-z0-9_-]+)")
        if v:
            return v, idx, src
        # known pattern like O-40412-1721
        v, idx, src=self._search_lines(lines, r"\b([A-Za-z]-?\d{3,}-\d{3,})\b")
        return v, idx, src


    def _tavo_header(self, lines: list[str]) -> dict:
        for i, line in enumerate(lines):
            m=re.search(r"(.{1,80}?)-\s*(آقای|آقاي|خانم)\s+(.{1,40}?)-\s*دکتر\s*([0-9]{1,3})\s*[:：]\s*سن", line)
            if not m:
                continue
            family=self._clean(m.group(1))
            title=m.group(2); given=self._clean(m.group(3)); age=int(m.group(4))
            sex="female" if title=="خانم" else "male"
            name=self._clean(f"{given} {family}")
            return {"patient_name": (name, .65, i, line.strip()), "sex": (sex, .75, i, line.strip()), "age": (age, .75, i, line.strip())}
        return {}

    def extract_structured(self, text: str) -> dict:
        # Normalize Persian/Arabic variants, presentation-form glyphs and digits so
        # labels, dates and IDs from real PDF text layers match reliably.
        t=normalize_persian(text or "")
        lines=t.split("\n")
        raw_allowed=getattr(settings,"allow_raw_national_id",False)

        # National ID
        nid, nid_idx, nid_src=self._search_lines(lines, r"(?:National\s*ID|کد\s*(?:ملی|ملي)|كد\s*ملي)\s*[:：]?\s*([0-9]{10})")
        if not nid:
            nid, nid_idx, nid_src=self._search_lines(lines, r"\b([0-9]{10})\b")
        if nid and nid_src and not raw_allowed:
            nid_src=nid_src.replace(nid, "*" * len(nid))  # never leak the raw ID via evidence

        # Main report date (prefer explicitly labelled dates), kept separate from print date.
        date, date_idx, date_src=self._search_lines(lines, r"(?:تاریخ\s*(?:پذیرش|گزارش)|تاريخ\s*(?:پذيرش|گزارش)|Report\s*Date|Date\s*of\s*test|Date)\s*[:：]?\s*(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")
        if not date:
            date, date_idx, date_src=self._search_lines(lines, r"(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")
        print_date, pd_idx, pd_src=self._search_lines(lines, r"(?:Print(?:ed)?(?:\s*On)?|تاریخ\s*چاپ|تاريخ\s*چاپ)\s*[:：]?\s*(?:\d{1,2}:\d{2}:\d{2}\s*-\s*)?([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})")

        name, name_idx, name_src=self._search_lines(lines, r"(?:Patient\s*Name|نام\s*(?:بیمار|بيمار)|Name)\s*[:：]?\s*([^\n]+)")
        tavo=self._tavo_header(lines)
        sex=None; age=None; sex_src=None; sex_idx=None; age_src=None; age_idx=None
        for i, line in enumerate(lines):
            m=re.search(r"\b(آقای|آقاي|خانم)\s+([^\n]+?)\s+سن\s*[:：]?\s*([0-9]{1,3})", line)
            if m:
                sex="female" if m.group(1)=="خانم" else "male"; sex_src=line.strip(); sex_idx=i
                if not name: name=m.group(2).strip(" -"); name_src=line.strip(); name_idx=i
                age=int(m.group(3)); age_src=line.strip(); age_idx=i
                break
        if not name and "patient_name" in tavo:
            name, _, name_idx, name_src=tavo["patient_name"]
        if age is None and "age" in tavo:
            age, _, age_idx, age_src=tavo["age"]
        if sex is None and "sex" in tavo:
            sex, _, sex_idx, sex_src=tavo["sex"]
        if sex is None:
            sv, si, ss=self._search_lines(lines, r"\b(Male|Female|آقای|آقاي|خانم)\b")
            if sv:
                low=sv.lower()
                sex="male" if (low=="male" or sv in ("آقای","آقاي")) else "female"; sex_src=ss; sex_idx=si
        if age is None:
            a, ai, asrc=self._search_lines(lines, r"(?:Age|سن)\s*[:：]?\s*([0-9]{1,3})(?:\s*سال)?")
            if a: age=int(a); age_src=asrc; age_idx=ai

        cal="jalali" if date and date.startswith("14") else ("gregorian" if date else None)
        center_value, center_conf, center_idx, center_src=self._center_name(lines)
        tracking, tr_idx, tr_src=self._tracking_number(lines)
        report_name, rn_idx, rn_src=self._search_lines(lines, r"(?:Test|Report|Exam)\s*[:：]\s*([^\n]+)")
        doctor, doc_idx, doc_src=self._search_lines(lines, r"(?:Doctor|Physician|پزشک|پزشك)\s*[:：]?\s*([^\n]+)")

        return {
            "patient_name": self._field(name, source_text=name_src, source_line_index=name_idx),
            "national_id": {"value": nid if raw_allowed else None, "hash": hash_national_id(nid) if nid else None,
                            "confidence": .9 if nid else 0.0,
                            "source_text": nid_src if nid else None, "source_line_index": nid_idx if nid else None},
            "date_of_test_or_report": self._field(date, .9, source_text=date_src, source_line_index=date_idx, calendar=cal),
            "print_date": self._field(print_date, .8, source_text=pd_src, source_line_index=pd_idx),
            "test_or_report_name": self._field(report_name, source_text=rn_src, source_line_index=rn_idx),
            "center_name": self._field(center_value, center_conf, source_text=center_src, source_line_index=center_idx),
            "doctor_name": self._field(doctor, source_text=doc_src, source_line_index=doc_idx),
            "age": self._field(age, .85, source_text=age_src, source_line_index=age_idx),
            "sex": self._field(sex, .85, source_text=sex_src, source_line_index=sex_idx),
            "tracking_number": self._field(tracking, source_text=tr_src, source_line_index=tr_idx),
        }

    def extract(self,text:str)->dict:
        s=self.extract_structured(text)
        return {k: (v.get("value") if isinstance(v,dict) else v) for k,v in s.items()} | {"national_id_hash": s["national_id"].get("hash")}
