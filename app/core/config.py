from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Medical Document Extraction MVP"
    database_url: str = Field(default="sqlite:///./medical_documents.db", alias="DATABASE_URL")
    storage_dir: str = Field(default="storage", alias="STORAGE_DIR")
    max_upload_mb: int = Field(default=20, alias="MAX_UPLOAD_MB")
    relevance_threshold: float = 0.15
    quality_poor_threshold: float = 0.25
    quality_good_threshold: float = 0.65
    pdf_text_threshold: int = Field(default=40, alias="PDF_TEXT_THRESHOLD")
    max_preprocess_pages: int = Field(default=5, alias="MAX_PREPROCESS_PAGES")
    ocr_backend: str = Field(default="tesseract", alias="OCR_BACKEND")
    enable_paddleocr: bool = Field(default=False, alias="ENABLE_PADDLEOCR")
    tesseract_lang: str = Field(default="eng+fas", alias="TESSERACT_LANG")
    paddleocr_lang: str = Field(default="en", alias="PADDLEOCR_LANG")
    allow_raw_national_id: bool = Field(default=False, alias="ALLOW_RAW_NATIONAL_ID")
    block_duplicate_uploads: bool = Field(default=False, alias="BLOCK_DUPLICATE_UPLOADS")
    class Config:
        env_file = ".env"
        extra = "ignore"
settings = Settings()
