import hashlib, shutil, uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
class StorageService:
    def __init__(self):
        self.root=Path(settings.storage_dir); (self.root/'originals').mkdir(parents=True,exist_ok=True); (self.root/'processed').mkdir(parents=True,exist_ok=True)
    def save_upload(self, upload: UploadFile) -> tuple[str,int,str]:
        suffix=Path(upload.filename or 'upload').suffix.lower(); path=self.root/'originals'/f"{uuid.uuid4().hex}{suffix}"
        h=hashlib.sha256(); size=0
        with path.open('wb') as f:
            while chunk:=upload.file.read(1024*1024):
                size+=len(chunk); h.update(chunk); f.write(chunk)
        upload.file.seek(0)
        return str(path), size, h.hexdigest()

    def save_file(self, src_path: str, copy: bool = True) -> tuple[str, int, str]:
        """Ingest an existing file from disk (used by the offline evaluation script).

        Computes size and SHA-256. By default copies the file into
        ``storage/originals`` so the original input is never modified; set
        ``copy=False`` to reference the file in place.
        """
        src=Path(src_path)
        data=src.read_bytes()
        size=len(data); digest=hashlib.sha256(data).hexdigest()
        if not copy:
            return str(src), size, digest
        dest=self.root/'originals'/f"{uuid.uuid4().hex}{src.suffix.lower()}"
        shutil.copyfile(src, dest)
        return str(dest), size, digest
