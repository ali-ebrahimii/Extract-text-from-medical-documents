from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Stateless Medical Document Extraction Service"
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
    debug_output_dir: str = Field(default="debug_output", alias="DEBUG_OUTPUT_DIR")
    debug_save_intermediate_files: bool = Field(default=False, alias="DEBUG_SAVE_INTERMEDIATE_FILES")
    file_url_allowed_hosts: str = Field(default="", alias="FILE_URL_ALLOWED_HOSTS")
    file_url_allow_private_hosts: bool = Field(default=False, alias="FILE_URL_ALLOW_PRIVATE_HOSTS")
    file_url_timeout_seconds: int = Field(default=15, alias="FILE_URL_TIMEOUT_SECONDS")
    file_url_max_redirects: int = Field(default=3, alias="FILE_URL_MAX_REDIRECTS")
    backend_file_list_url_template: str = Field(default="", alias="BACKEND_FILE_LIST_URL_TEMPLATE")
    backend_file_fetch_url_template: str = Field(default="", alias="BACKEND_FILE_FETCH_URL_TEMPLATE")
    backend_api_token: str = Field(default="", alias="BACKEND_API_TOKEN")
    backend_api_timeout_seconds: int = Field(default=15, alias="BACKEND_API_TIMEOUT_SECONDS")
    backend_api_max_files: int = Field(default=50, alias="BACKEND_API_MAX_FILES")
    backend_api_file_response_mode: str = Field(default="auto", alias="BACKEND_API_FILE_RESPONSE_MODE")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
