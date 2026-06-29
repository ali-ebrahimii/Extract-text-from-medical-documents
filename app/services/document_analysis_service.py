from dataclasses import dataclass
from pathlib import Path
import fitz
from app.core.config import settings

@dataclass
class DocumentAnalysisResult:
    file_type: str
    pdf_type: str | None = None
    page_count: int = 1
    has_text_layer: bool = False
    estimated_text_length: int = 0
    needs_rendering: bool = False
    should_skip_image_quality_check: bool = False
    text_sample: str = ""

class DocumentAnalysisService:
    def analyze(self, path: str, filename: str | None = None) -> DocumentAnalysisResult:
        ext = Path(filename or path).suffix.lower()
        if ext == ".pdf":
            try:
                doc = fitz.open(path)
                page_count = doc.page_count
                sample_parts = []
                total_len = 0
                for page in doc:
                    txt = page.get_text() or ""
                    total_len += len(txt.strip())
                    if len("\n".join(sample_parts)) < 4000:
                        sample_parts.append(txt)
                doc.close()
                threshold = getattr(settings, "pdf_text_threshold", 80)
                has_text = total_len >= threshold
                return DocumentAnalysisResult(
                    file_type="pdf", pdf_type="text_pdf" if has_text else "scanned_pdf",
                    page_count=page_count, has_text_layer=has_text,
                    estimated_text_length=total_len, needs_rendering=not has_text,
                    should_skip_image_quality_check=has_text, text_sample="\n".join(sample_parts)[:4000]
                )
            except Exception:
                return DocumentAnalysisResult(file_type="pdf", pdf_type="unknown", page_count=0, needs_rendering=True)
        return DocumentAnalysisResult(file_type="image", page_count=1, needs_rendering=False, should_skip_image_quality_check=False)
