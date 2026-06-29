from dataclasses import dataclass
from pathlib import Path
from PIL import Image
import fitz
from app.core.config import settings
from app.core.enums import DocumentStatus
SUPPORTED={'.pdf':'application/pdf','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}
MIME_ALIASES={'image/jpg':'image/jpeg'}
@dataclass
class ValidationResult:
    is_valid: bool; status: str; reason: str|None=None
class FileValidationService:
    def validate(self,path:str,filename:str,mime_type:str|None=None)->ValidationResult:
        p=Path(path); ext=Path(filename).suffix.lower()
        if ext not in SUPPORTED: return ValidationResult(False, DocumentStatus.UNSUPPORTED_FILE_TYPE.value, 'Unsupported file type')
        if not p.exists() or p.stat().st_size==0: return ValidationResult(False, DocumentStatus.INVALID_FILE.value, 'Empty or missing file')
        if p.stat().st_size > settings.max_upload_mb*1024*1024: return ValidationResult(False, DocumentStatus.SECURITY_REJECTED.value, 'File too large')
        normalized_mime=MIME_ALIASES.get(mime_type or '', mime_type)
        if normalized_mime and normalized_mime not in (SUPPORTED[ext], 'application/octet-stream'): return ValidationResult(False, DocumentStatus.INVALID_FILE.value, 'MIME type does not match supported types')
        try:
            if ext=='.pdf':
                doc=fitz.open(path)
                if doc.needs_pass: return ValidationResult(False, DocumentStatus.INVALID_FILE.value, 'Password-protected PDF')
                _=doc.page_count; doc.close()
            else:
                with Image.open(path) as img: img.verify()
        except Exception as e:
            return ValidationResult(False, DocumentStatus.INVALID_FILE.value, f'Unreadable file: {e}')
        return ValidationResult(True, DocumentStatus.UPLOADED.value)
