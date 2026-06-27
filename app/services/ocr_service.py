from dataclasses import dataclass
from pathlib import Path
import fitz
@dataclass
class OCRResult:
    success: bool; text: str; confidence: float; error: str|None=None
class OCRService:
    def extract(self,path:str)->OCRResult:
        ext=Path(path).suffix.lower()
        if ext=='.pdf':
            try:
                doc=fitz.open(path); text='\n'.join(p.get_text() for p in doc); doc.close()
                return OCRResult(bool(text.strip()), text, .9 if text.strip() else .0, None if text.strip() else 'No embedded text found; image OCR required')
            except Exception as e: return OCRResult(False,'',0,str(e))
        try:
            import pytesseract
            from PIL import Image
            text=pytesseract.image_to_string(Image.open(path))
            return OCRResult(bool(text.strip()), text, .65 if text.strip() else 0, None if text.strip() else 'Tesseract returned no text')
        except Exception as e:
            return OCRResult(False,'',0,f'pytesseract unavailable or failed: {e}')
