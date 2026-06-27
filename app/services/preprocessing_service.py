from dataclasses import dataclass
from pathlib import Path
import uuid, cv2, fitz, numpy as np
from app.core.config import settings
@dataclass
class PreprocessingResult:
    success: bool; output_path: str|None; steps: list[str]; error: str|None=None
class PreprocessingService:
    def preprocess(self,path:str)->PreprocessingResult:
        try:
            ext=Path(path).suffix.lower(); out=Path(settings.storage_dir)/'processed'/f"{uuid.uuid4().hex}.png"; out.parent.mkdir(parents=True,exist_ok=True)
            if ext=='.pdf':
                doc=fitz.open(path)
                if doc[0].get_text().strip(): doc.close(); return PreprocessingResult(True,path,['text_pdf_no_preprocessing'])
                pix=doc[0].get_pixmap(matrix=fitz.Matrix(2,2)); img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w,pix.n); doc.close(); img=cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else: img=cv2.imread(path)
            gray=cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); eq=cv2.equalizeHist(gray); den=cv2.fastNlMeansDenoising(eq); thr=cv2.adaptiveThreshold(den,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,11); cv2.imwrite(str(out),thr)
            return PreprocessingResult(True,str(out),['grayscale','contrast_enhancement','denoising','adaptive_threshold'])
        except Exception as e: return PreprocessingResult(False,None,[],str(e))
