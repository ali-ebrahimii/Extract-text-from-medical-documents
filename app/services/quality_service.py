from dataclasses import dataclass, field
from pathlib import Path
import numpy as np, fitz
@dataclass
class QualityResult:
    status:str; overall_quality_score:float; is_acceptable:bool; issues:list[str]; blur_score:float; brightness_score:float; contrast_score:float; resolution_score:float; crop_score:float=0.8; orientation_score:float=0.8; ocr_readability_score:float=0.5; is_fixable:bool=True; metrics:dict=field(default_factory=dict)
def _cv2():
    return __import__("cv2")

class QualityService:
    def _gray(self,path:str):
        if Path(path).suffix.lower()=='.pdf':
            doc=fitz.open(path); pix=doc[0].get_pixmap(matrix=fitz.Matrix(1,1), alpha=False); arr=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w,pix.n); doc.close(); cv2=_cv2(); return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        cv2=_cv2(); return cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    def assess(self,path:str)->QualityResult:
        try:
            gray=self._gray(path)
            if gray is None: raise ValueError('unreadable_image')
            h,w=gray.shape[:2]; cv2=_cv2(); var=cv2.Laplacian(gray, cv2.CV_64F).var(); mean=float(np.mean(gray)); std=float(np.std(gray))
            blur=min(1.0,var/500); brightness=1-abs(mean-127)/127; contrast=min(1.0,std/80); res=min(1.0,(w*h)/(1000*1000)); overall=max(0,min(1,blur*.35+brightness*.2+contrast*.25+res*.2))
            issues=[]
            if blur<.18: issues.append('severe_blur')
            if contrast<.25: issues.append('low_contrast')
            if mean<45: issues.append('too_dark')
            if mean>220: issues.append('too_bright')
            if res<.1: issues.append('low_resolution')
            if h>w*1.4: issues.append('possible_rotation')
            unreadable=blur<.05 and contrast<.10
            if unreadable: issues.append('unreadable_image')
            status='good_quality' if overall>=.65 else ('needs_preprocessing' if overall>=.18 and not unreadable else 'poor_quality')
            return QualityResult(status, overall, status!='poor_quality', issues, blur, brightness, contrast, res, is_fixable=status!='poor_quality', metrics={'width':w,'height':h,'brightness_mean':mean,'contrast_std':std,'laplacian_variance':var})
        except Exception as e: return QualityResult('poor_quality',0,False,['unreadable_image',str(e)],0,0,0,0,False,{})
