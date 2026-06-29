from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from app.models.document import Base
class DocumentPreprocessing(Base):
    __tablename__="document_preprocessing"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    preprocessing_required=Column(Boolean); preprocessing_applied=Column(Boolean); quality_score_before=Column(Float); quality_score_after=Column(Float); preprocessing_steps=Column(JSON); original_page_path=Column(String); preprocessed_page_path=Column(String); preprocessing_status=Column(String); preprocessing_error=Column(Text); created_at=Column(DateTime, default=datetime.utcnow)
