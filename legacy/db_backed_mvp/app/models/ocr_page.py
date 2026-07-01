from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.models.document import Base
class OCRPage(Base):
    __tablename__="ocr_pages"
    id=Column(Integer, primary_key=True)
    document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    page_number=Column(Integer, nullable=False)
    source_path=Column(String)
    ocr_text=Column(Text)
    ocr_confidence=Column(Float)
    created_at=Column(DateTime, default=datetime.utcnow)
