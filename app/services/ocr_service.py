from dataclasses import dataclass, field
from pathlib import Path
import fitz
from app.core.config import settings

@dataclass
class OCRPageResult:
    page_number:int; text:str; confidence:float; source_path:str|None=None
@dataclass
class OCRResult:
    success:bool; text:str; confidence:float; pages:list[OCRPageResult]=field(default_factory=list); error:str|None=None; warnings:list[str]=field(default_factory=list)

class OCRService:
    MISSING="Image OCR engine is not available. Install Tesseract or configure PaddleOCR."

    def extract_pdf_text(self,path:str)->OCRResult:
        try:
            doc=fitz.open(path); pages=[]
            for i,p in enumerate(doc,1):
                txt=p.get_text() or ""; pages.append(OCRPageResult(i,txt,.95 if txt.strip() else 0,path))
            doc.close(); text="\f".join(p.text for p in pages)
            return OCRResult(bool(text.strip()), text, .95 if text.strip() else 0, pages, None if text.strip() else "No embedded text found; image OCR required")
        except Exception as e: return OCRResult(False,"",0,[],str(e))

    def _backend(self)->str:
        return getattr(settings,"ocr_backend","tesseract").lower()

    def _should_try_paddle(self)->bool:
        backend=self._backend()
        if backend=="paddleocr": return True
        if backend=="auto": return bool(getattr(settings,"enable_paddleocr",False))
        # "tesseract" (and any unknown value): Tesseract only.
        return False

    def _paddle_text(self,path:str):
        try:
            from paddleocr import PaddleOCR
            lang=getattr(settings,"paddleocr_lang","en")
            ocr=PaddleOCR(use_angle_cls=True, lang=lang)
            result=ocr.ocr(path, cls=True); lines=[]; conf=[]
            for block in result or []:
                for item in block or []:
                    lines.append(item[1][0]); conf.append(float(item[1][1]))
            return "\n".join(lines), (sum(conf)/len(conf) if conf else 0)
        except Exception: return None

    def _tesseract_text(self,path:str):
        lang=getattr(settings,"tesseract_lang","eng")
        try:
            import pytesseract
            from PIL import Image
            img=Image.open(path)
            data=pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
            words=[w for w in data.get('text',[]) if w and w.strip()]
            confs=[float(c) for c in data.get('conf',[]) if str(c).replace('.','',1).lstrip('-').isdigit() and float(c)>=0]
            text=" ".join(words) if words else pytesseract.image_to_string(img, lang=lang)
            conf=(sum(confs)/len(confs)/100) if confs else (.6 if text.strip() else 0)
            return text, conf
        except Exception as e:
            return None, (f"{e} (check TESSERACT_LANG='{lang}' and that the matching "
                          "tesseract language packs are installed)")

    def extract_image_text(self,path:str,page_number:int=1)->OCRResult:
        warnings:list[str]=[]
        if self._should_try_paddle():
            p=self._paddle_text(path)
            if p is not None:
                text,conf=p
                return OCRResult(bool(text.strip()),text,conf,[OCRPageResult(page_number,text,conf,path)],None if text.strip() else "PaddleOCR returned no text",warnings)
            # PaddleOCR requested but unavailable -> fall back to Tesseract with a warning.
            warnings.append("paddleocr_failed_fell_back_to_tesseract")
        text,conf_or_err=self._tesseract_text(path)
        if text is None:
            return OCRResult(False,"",0,[],f"{self.MISSING} ({conf_or_err})",warnings)
        conf=conf_or_err
        return OCRResult(bool(text.strip()),text,conf,[OCRPageResult(page_number,text,conf,path)],None if text.strip() else "Tesseract returned no text",warnings)

    def extract_images_text(self,paths:list[str])->OCRResult:
        pages=[]; errs=[]; warnings:list[str]=[]
        for i,p in enumerate(paths,1):
            r=self.extract_image_text(p,i); pages.extend(r.pages)
            if r.error: errs.append(r.error)
            for w in r.warnings:
                if w not in warnings: warnings.append(w)
        text="\f".join(p.text for p in pages); conf=sum((p.confidence for p in pages),0)/len(pages) if pages else 0
        return OCRResult(bool(text.strip()),text,conf,pages,"; ".join(errs) if errs and not text.strip() else None,warnings)

    def extract_any(self,path:str,analysis_result=None,preprocessed_paths:list[str]|None=None)->OCRResult:
        if preprocessed_paths: return self.extract_images_text(preprocessed_paths)
        if Path(path).suffix.lower()=='.pdf' and getattr(analysis_result,'pdf_type',None)=='text_pdf': return self.extract_pdf_text(path)
        if Path(path).suffix.lower()=='.pdf': return self.extract_pdf_text(path)
        return self.extract_image_text(path)

    def extract(self,path:str)->OCRResult: return self.extract_any(path)
