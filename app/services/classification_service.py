from dataclasses import dataclass
from app.core.enums import DocumentType
@dataclass
class ClassificationResult: document_type: str; confidence: float
class ClassificationService:
    def classify(self,text:str)->ClassificationResult:
        t=text.lower()
        scores={DocumentType.LAB.value:sum(x in t for x in ['cbc','wbc','rbc','hemoglobin','fbs','tsh','reference range','result','unit','biochemistry','hematology']), DocumentType.PAP_SMEAR.value:sum(x in t for x in ['pap smear','nilm','asc-us','lsil','hsil','specimen adequacy']), DocumentType.RADIOLOGY.value:sum(x in t for x in ['radiology','ultrasound','mri','ct','x-ray','findings','impression'])}
        best=max(scores,key=scores.get)
        return ClassificationResult(best, min(1,scores[best]/4)) if scores[best] else ClassificationResult(DocumentType.UNKNOWN_MEDICAL.value,.3)
