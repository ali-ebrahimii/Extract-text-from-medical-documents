from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
import fitz

# Explicit phrase list so multi-word terms like "کد ملی" are not split.
PERSIAN_TERMS = [
    "آزمایشگاه",
    "آزمايشگاه",
    "پاتوبیولوژی",
    "پاتوبیولوژي",
    "بیمارستان",
    "بيمارستان",
    "درمانگاه",
    "کلینیک",
    "کد ملی",
    "کد ملي",
    "كد ملي",
    "نام بیمار",
    "نام بيمار",
    "پزشک",
    "پزشك",
    "تاریخ پذیرش",
    "تاريخ پذيرش",
    "تاریخ گزارش",
    "تاريخ گزارش",
    "نتیجه",
    "نتيجه",
    "محدوده نرمال",
    "محدوده طبیعی",
    "رادیولوژی",
    "راديولوژي",
    "سونوگرافی",
    "سونوگرافي",
    "پاتولوژی",
    "پاتولوژي",
    "نمونه",
    "خون",
    "ادرار",
]
ENGLISH_TERMS = ["Laboratory","Pathobiology","Lab","CBC","WBC","RBC","Hemoglobin","Platelets","Hematology","Biochemistry","FBS","Glucose","TSH","SGOT","SGPT","AST","ALT","Reference Range","Normal Range","Result","Unit","Method","Pap smear","Pathology","Radiology","Ultrasound","MRI","CT","X-ray","Findings","Impression","Specimen"]


def normalize_persian(text: str) -> str:
    """Normalize Arabic/Persian character variants and collapse whitespace.

    - NFKC normalization (folds Arabic presentation-form glyphs to canonical
      letters, which PDF text layers often contain)
    - Arabic Yeh (ي) -> Persian Yeh (ی)
    - Arabic Kaf (ك) -> Persian Kaf (ک)
    - collapse runs of intra-line whitespace (newlines are preserved so callers
      can still reason about line structure)
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[^\S\n]+", " ", text)
    return text


@dataclass
class RelevanceResult:
    is_medical_document: bool
    relevance_score: float
    detected_keywords: list[str]
    detected_document_signals: list[str]
    rejection_reason: str | None = None
    text_used_for_relevance: str = ""
    reason: str = ""

class RelevanceService:
    def sample_text(self, path: str, filename: str) -> str:
        if Path(filename).suffix.lower() == ".pdf":
            try:
                doc = fitz.open(path); text = "\n".join(page.get_text() for page in list(doc)[:2]); doc.close(); return text
            except Exception: return ""
        return ""

    def check_from_text(self, text: str, filename: str | None = None) -> RelevanceResult:
        haystack = f"{filename or ''}\n{text or ''}"
        # Normalize Persian variants so e.g. "تاريخ پذيرش" matches "تاریخ پذیرش".
        norm = normalize_persian(haystack)
        low = norm.lower()
        found: list[str] = []
        for k in ENGLISH_TERMS:
            if k.lower() in low and k not in found:
                found.append(k)
        for k in PERSIAN_TERMS:
            nk = normalize_persian(k)
            if nk and nk in norm and k not in found:
                found.append(k)
        score = min(1.0, len(found) / 4.0)
        ok = score >= 0.15
        reason = f"Detected {len(found)} medical keyword(s)" if ok else "No medical document signals detected in extracted text"
        return RelevanceResult(ok, score, found, found[:5], None if ok else reason, haystack[:2000], reason)

    def check(self, path: str, filename: str, ocr_text: str | None = None) -> RelevanceResult:
        return self.check_from_text(ocr_text if ocr_text is not None else self.sample_text(path, filename), filename)
