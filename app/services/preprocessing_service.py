from dataclasses import dataclass, field
from pathlib import Path
import uuid, fitz, numpy as np
from PIL import Image, ImageOps
from app.core.config import settings

@dataclass
class PreprocessingResult:
    success: bool
    output_path: str | None = None
    output_paths: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    error: str | None = None

@dataclass
class RenderResult:
    """Result of rendering PDF pages to images for OCR (no image enhancement)."""
    success: bool
    output_paths: list[str] = field(default_factory=list)
    page_count: int = 0
    error: str | None = None

def _cv2():
    return __import__("cv2")

class PreprocessingService:
    def render_pdf_pages(self, path: str, document_id: int | None = None, max_pages: int | None = None, output_dir: str | None = None) -> RenderResult:
        """Render PDF pages to PNG images for OCR.

        This is rendering only — it does NOT apply image-enhancement
        preprocessing (denoise/threshold/sharpen). Use it for good-quality
        scanned PDFs that need page images for OCR without altering the pixels.
        Only up to ``max_pages`` (default ``settings.max_preprocess_pages``)
        pages are rendered; fewer if the PDF has fewer pages.
        """
        try:
            base=Path(output_dir) if output_dir else Path(settings.storage_dir)/'rendered'/str(document_id or uuid.uuid4().hex); base.mkdir(parents=True,exist_ok=True)
            limit=max_pages or settings.max_preprocess_pages
            doc=fitz.open(path); paths=[]
            for i,page in enumerate(doc[:limit], start=1):
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
                out=base/f"page_{i:03d}.png"; pix.save(str(out)); paths.append(str(out))
            doc.close()
            return RenderResult(True, paths, len(paths), None)
        except Exception as e:
            return RenderResult(False, [], 0, str(e))

    def _process_array(self, img, out: Path) -> list[str]:
        cv2=_cv2(); steps=[]
        if len(img.shape)==3:
            gray=cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); steps.append('grayscale')
        else: gray=img
        den=cv2.fastNlMeansDenoising(gray); steps.append('denoise')
        clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)); eq=clahe.apply(den); steps.append('contrast_enhancement')
        thr=cv2.adaptiveThreshold(eq,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,11); steps.append('adaptive_threshold')
        sharp=cv2.filter2D(thr,-1,np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])); steps.append('sharpening')
        cv2.imwrite(str(out), sharp); return steps
    def preprocess(self,path:str, document_id:int|None=None, max_pages:int|None=None, output_dir: str | None = None)->PreprocessingResult:
        try:
            ext=Path(path).suffix.lower(); base=Path(output_dir) if output_dir else Path(settings.storage_dir)/'processed'/str(document_id or uuid.uuid4().hex); base.mkdir(parents=True,exist_ok=True)
            if ext=='.pdf':
                doc=fitz.open(path); paths=[]; steps=['render_pdf_pages']
                for i,page in enumerate(doc[:max_pages or settings.max_preprocess_pages], start=1):
                    pix=page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
                    img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w,pix.n)
                    cv2=_cv2(); img=cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                    out=base/f"page_{i:03d}.png"; page_steps=self._process_array(img,out); paths.append(str(out))
                doc.close(); return PreprocessingResult(True, paths[0] if paths else None, paths, steps+page_steps, None)
            pil=ImageOps.exif_transpose(Image.open(path)); steps=['auto_orientation']
            cv2=_cv2(); img=cv2.cvtColor(np.array(pil.convert('RGB')), cv2.COLOR_RGB2BGR)
            out=base/'page_001.png'; steps += self._process_array(img,out)
            return PreprocessingResult(True,str(out),[str(out)],steps,None)
        except Exception as e: return PreprocessingResult(False,None,[],[],str(e))
