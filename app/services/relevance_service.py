import fitz
from dataclasses import dataclass
from pathlib import Path
from app.dictionaries.medical_keywords import ENGLISH_MEDICAL_KEYWORDS, PERSIAN_MEDICAL_KEYWORDS
@dataclass
class RelevanceResult:
    is_medical_document: bool; relevance_score: float; detected_keywords: list[str]; detected_document_signals: list[str]; rejection_reason: str|None=None
class RelevanceService:
    def sample_text(self,path:str,filename:str)->str:
        if Path(filename).suffix.lower()=='.pdf':
            try:
                doc=fitz.open(path); text='\n'.join(page.get_text() for page in doc[:2]); doc.close(); return text
            except Exception: return filename
        return filename
    def check(self,path:str,filename:str,ocr_text:str|None=None)->RelevanceResult:
        text=f"{filename}\n{ocr_text or self.sample_text(path,filename)}".lower(); kws=ENGLISH_MEDICAL_KEYWORDS+PERSIAN_MEDICAL_KEYWORDS
        found=[k for k in kws if k.lower() in text]
        score=min(1.0, len(found)/5)
        return RelevanceResult(score>=0.15, score, found, found[:3], None if score>=0.15 else 'No medical document signals detected')
