from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.document import Base
class RadiologyReport(Base):
    __tablename__="radiology_reports"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    imaging_modality=Column(String); body_part_or_exam_name=Column(String); findings=Column(Text); impression_conclusion=Column(Text); full_narrative_report=Column(Text); radiologist_name=Column(String); confidence=Column(Float); created_at=Column(DateTime, default=datetime.utcnow)
    document=relationship("MedicalDocument", back_populates="radiology_reports")
