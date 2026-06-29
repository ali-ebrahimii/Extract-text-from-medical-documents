from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.document import Base
class ReviewTask(Base):
    __tablename__="review_tasks"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    reason=Column(Text); priority=Column(Integer, default=3); assigned_to=Column(String); status=Column(String, default="open"); created_at=Column(DateTime, default=datetime.utcnow); reviewed_at=Column(DateTime)
    document=relationship("MedicalDocument", back_populates="review_tasks")
