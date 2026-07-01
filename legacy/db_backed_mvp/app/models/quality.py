from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from app.models.document import Base
class DocumentQualityCheck(Base):
    __tablename__="document_quality_checks"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    blur_score=Column(Float); brightness_score=Column(Float); contrast_score=Column(Float); resolution_score=Column(Float); crop_score=Column(Float); orientation_score=Column(Float); ocr_readability_score=Column(Float); overall_quality_score=Column(Float); is_acceptable=Column(Boolean); issues=Column(JSON); created_at=Column(DateTime, default=datetime.utcnow)
class DocumentRelevanceCheck(Base):
    __tablename__="document_relevance_checks"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    is_medical_document=Column(Boolean); relevance_score=Column(Float); detected_keywords=Column(JSON); detected_document_signals=Column(JSON); rejection_reason=Column(String); created_at=Column(DateTime, default=datetime.utcnow)
