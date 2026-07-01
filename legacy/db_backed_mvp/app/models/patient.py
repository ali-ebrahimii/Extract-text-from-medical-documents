from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.models.document import Base
class DocumentPatient(Base):
    __tablename__ = "document_patients"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    patient_name=Column(String); patient_name_confidence=Column(Float); national_id_encrypted=Column(String); national_id_hash=Column(String); national_id_confidence=Column(Float)
    age=Column(Integer); sex=Column(String); created_at=Column(DateTime, default=datetime.utcnow)
    document=relationship("MedicalDocument", back_populates="patients")
