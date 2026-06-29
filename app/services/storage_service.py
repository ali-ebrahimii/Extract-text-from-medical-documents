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
