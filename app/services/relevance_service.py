from dataclasses import dataclass
from pathlib import Path
import fitz

PERSIAN_TERMS = """آزمایشگاه آزمايشگاه پاتوبیولوژی پاتوبیولوژي بیمارستان بيمارستان درمانگاه کلینیک كد ملي کد ملی نام نام بیمار پزشک پزشك تاریخ پذیرش تاريخ پذيرش نتیجه نتيجه محدوده نرمال محدوده طبیعی رادیولوژی راديولوژي سونوگرافی سونوگرافي پاتولوژی پاتولوژي نمونه خون ادرار""".split()
ENGLISH_TERMS = ["Laboratory","Pathobiology","Lab","CBC","WBC","RBC","Hemoglobin","Platelets","Hematology","Biochemistry","FBS","Glucose","TSH","SGOT","SGPT","AST","ALT","Reference Range","Normal Range","Result","Unit","Method","Pap smear","Pathology","Radiology","Ultrasound","MRI","CT","X-ray","Findings","Impression","Specimen"]

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
        low = haystack.lower()
        kws = ENGLISH_TERMS + PERSIAN_TERMS
        found = []
        for k in kws:
            if (k.lower() if k.isascii() else k) in (low if k.isascii() else haystack):
                if k not in found: found.append(k)
        score = min(1.0, len(found) / 4.0)
        ok = score >= 0.15
        reason = f"Detected {len(found)} medical keyword(s)" if ok else "No medical document signals detected in extracted text"
        return RelevanceResult(ok, score, found, found[:5], None if ok else reason, haystack[:2000], reason)

    def check(self, path: str, filename: str, ocr_text: str | None = None) -> RelevanceResult:
        return self.check_from_text(ocr_text if ocr_text is not None else self.sample_text(path, filename), filename)
