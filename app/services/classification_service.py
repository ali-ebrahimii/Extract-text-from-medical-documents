from dataclasses import dataclass
from app.core.enums import DocumentType

@dataclass
class ClassificationResult:
    document_type: str
    confidence: float
    matched_signals: list[str]
    reason: str

class ClassificationService:
    SIGNALS = {
        DocumentType.LAB.value: ["CBC","WBC","RBC","Hemoglobin","Platelets","FBS","TSH","SGOT","SGPT","AST","ALT","Biochemistry","Hematology","Result","Unit","Reference Range","Normal Range","آزمایشگاه","آزمايشگاه","پاتوبیولوژی","نتيجه","نتیجه","محدوده نرمال"],
        DocumentType.PAP_SMEAR.value: ["Pap smear","NILM","ASC-US","LSIL","HSIL","specimen adequacy","HPV","پاپ اسمیر","پاپ اسمير"],
        DocumentType.RADIOLOGY.value: ["Radiology","Ultrasound","Sonography","MRI","CT","X-ray","Findings","Impression","رادیولوژی","راديولوژي","سونوگرافی","سونوگرافي","ام آر آی","سی تی"],
    }
    def classify(self, text: str) -> ClassificationResult:
        hay = text or ""; low = hay.lower(); best_type = DocumentType.UNKNOWN_MEDICAL.value; best=[]
        for dtype, signals in self.SIGNALS.items():
            matched=[s for s in signals if (s.lower() if s.isascii() else s) in (low if s.isascii() else hay)]
            if len(matched)>len(best): best_type=dtype; best=matched
        if not best: return ClassificationResult(DocumentType.UNKNOWN_MEDICAL.value,.3,[],"No strong document-type signals found")
        return ClassificationResult(best_type, min(1.0, len(best)/5), best, f"Matched {len(best)} {best_type} signal(s)")
