from dataclasses import dataclass, field
from pathlib import Path
import numpy as np, fitz

# Issues that image-enhancement preprocessing can plausibly fix.
_FIXABLE_ISSUES = {"low_contrast", "too_dark", "too_bright", "possible_rotation", "severe_blur"}
# Issues that cannot be recovered by preprocessing (no detail to restore).
_HARD_FAIL_ISSUES = {"unreadable_image", "low_resolution"}


@dataclass
class QualityResult:
    status:str; overall_quality_score:float; is_acceptable:bool; issues:list[str]; blur_score:float; brightness_score:float; contrast_score:float; resolution_score:float; crop_score:float=0.8; orientation_score:float=0.8; ocr_readability_score:float=0.5; is_fixable:bool=True; metrics:dict=field(default_factory=dict)
    # Page-level summary (populated by assess_many for multi-page scanned PDFs).
    page_scores:list[float]=field(default_factory=list)
    page_issues:list[dict]=field(default_factory=list)
    worst_page_number:int|None=None
    average_quality_score:float|None=None
    min_quality_score:float|None=None
    num_pages:int=1


def _cv2():
    return __import__("cv2")


class QualityService:
    def _gray_from_pdf_page(self, page):
        pix=page.get_pixmap(matrix=fitz.Matrix(1,1), alpha=False)
        arr=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w,pix.n)
        cv2=_cv2(); return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    def _gray(self,path:str):
        if Path(path).suffix.lower()=='.pdf':
            doc=fitz.open(path); gray=self._gray_from_pdf_page(doc[0]); doc.close(); return gray
        cv2=_cv2(); return cv2.imread(path, cv2.IMREAD_GRAYSCALE)

    def _assess_gray(self, gray) -> QualityResult:
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
        if overall>=.65:
            status='good_quality'; is_acceptable=True; is_fixable=False
        elif overall>=.18 and not unreadable:
            status='needs_preprocessing'; is_acceptable=True; is_fixable=True
        else:
            status='poor_quality'; is_acceptable=False
            hard_fail=any(i in _HARD_FAIL_ISSUES for i in issues)
            is_fixable=(not hard_fail) and any(i in _FIXABLE_ISSUES for i in issues)
        return QualityResult(status, overall, is_acceptable, issues, blur, brightness, contrast, res, is_fixable=is_fixable, metrics={'width':w,'height':h,'brightness_mean':mean,'contrast_std':std,'laplacian_variance':var})

    def assess(self,path:str)->QualityResult:
        try:
            return self._assess_gray(self._gray(path))
        except Exception as e:
            return QualityResult('poor_quality',0,False,['unreadable_image',str(e)],0,0,0,0,is_fixable=False,metrics={})

    def assess_many(self, paths:list[str]) -> QualityResult:
        """Assess multiple page images and produce a conservative document-level summary.

        Document status/fixability follow the worst page; the overall score is the
        average. Per-page details are kept on the result and folded into ``issues``
        so they can be persisted in the quality-check JSON column.
        """
        if not paths:
            return QualityResult('poor_quality',0,False,['no_pages'],0,0,0,0,is_fixable=False)
        return self._summarize([self.assess(p) for p in paths])

    def assess_pdf_pages(self, path:str, max_pages:int|None=None) -> QualityResult:
        """Render up to ``max_pages`` PDF pages and assess them page-by-page."""
        try:
            doc=fitz.open(path); grays=[]
            for page in (doc[:max_pages] if max_pages else doc):
                grays.append(self._gray_from_pdf_page(page))
            doc.close()
        except Exception as e:
            return QualityResult('poor_quality',0,False,['unreadable_image',str(e)],0,0,0,0,is_fixable=False)
        per_page=[self._safe_assess_gray(g) for g in grays]
        return self._summarize(per_page)

    def _safe_assess_gray(self, gray) -> QualityResult:
        try:
            return self._assess_gray(gray)
        except Exception as e:
            return QualityResult('poor_quality',0,False,['unreadable_image',str(e)],0,0,0,0,is_fixable=False)

    def _summarize(self, per_page:list[QualityResult]) -> QualityResult:
        if not per_page:
            return QualityResult('poor_quality',0,False,['no_pages'],0,0,0,0,is_fixable=False)
        scores=[r.overall_quality_score for r in per_page]
        avg=float(sum(scores)/len(scores)); mn=float(min(scores))
        worst_idx=min(range(len(per_page)), key=lambda i: per_page[i].overall_quality_score)
        worst=per_page[worst_idx]
        page_issues=[{"page_number":i+1,"status":r.status,"score":round(r.overall_quality_score,3),"issues":r.issues} for i,r in enumerate(per_page)]
        issues=sorted({iss for r in per_page for iss in r.issues})
        issues=issues+[f"page{i+1}:{r.status}({round(r.overall_quality_score,3)})" for i,r in enumerate(per_page)]
        return QualityResult(
            status=worst.status, overall_quality_score=avg, is_acceptable=all(r.is_acceptable for r in per_page),
            issues=issues, blur_score=worst.blur_score, brightness_score=worst.brightness_score,
            contrast_score=worst.contrast_score, resolution_score=worst.resolution_score, is_fixable=worst.is_fixable,
            metrics={"average_quality_score":avg,"min_quality_score":mn,"worst_page_number":worst_idx+1},
            page_scores=[round(s,3) for s in scores], page_issues=page_issues,
            worst_page_number=worst_idx+1, average_quality_score=avg, min_quality_score=mn, num_pages=len(per_page),
        )
