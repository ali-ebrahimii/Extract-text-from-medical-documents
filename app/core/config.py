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
    class Config:
        env_file = ".env"
        extra = "ignore"
settings = Settings()
