from dataclasses import dataclass
from pathlib import Path
import cv2, numpy as np, fitz
@dataclass
class QualityResult:
    status: str; overall_quality_score: float; is_acceptable: bool; issues: list[str]; blur_score: float; brightness_score: float; contrast_score: float; resolution_score: float; crop_score: float=0.8; orientation_score: float=0.8; ocr_readability_score: float=0.5
class QualityService:
    def _image_path_for_pdf(self,path:str):
        doc=fitz.open(path); page=doc[0]; pix=page.get_pixmap(matrix=fitz.Matrix(1,1)); arr=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w,pix.n); doc.close(); return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    def assess(self,path:str)->QualityResult:
        try:
            ext=Path(path).suffix.lower(); gray=self._image_path_for_pdf(path) if ext=='.pdf' else cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if gray is None: raise ValueError('not an image')
            h,w=gray.shape[:2]; blur=min(1.0, cv2.Laplacian(gray, cv2.CV_64F).var()/500); brightness=1-abs(float(np.mean(gray))-127)/127; contrast=min(1.0, float(np.std(gray))/80); res=min(1.0,(w*h)/(1000*1000)); overall=max(0,min(1,(blur*.35+brightness*.2+contrast*.25+res*.2)))
            issues=[]
            if blur<.25: issues.append('blur')
            if brightness<.35: issues.append('brightness')
            if contrast<.25: issues.append('contrast')
            if res<.1: issues.append('low_resolution')
            status='good_quality' if overall>=.65 else ('needs_preprocessing' if overall>=.20 else 'poor_quality')
            return QualityResult(status, overall, status!='poor_quality', issues, blur, brightness, contrast, res)
        except Exception as e:
            return QualityResult('poor_quality',0,False,[str(e)],0,0,0,0)
