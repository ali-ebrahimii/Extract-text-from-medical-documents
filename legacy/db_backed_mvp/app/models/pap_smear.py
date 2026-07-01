from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.document import Base
class PapSmearReport(Base):
    __tablename__="pap_smear_reports"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    specimen_adequacy=Column(String); interpretation_result=Column(String); full_narrative_report=Column(Text); recommendation=Column(Text); hpv_result=Column(String); doctor_or_pathologist_name=Column(String); confidence=Column(Float); created_at=Column(DateTime, default=datetime.utcnow)
    document=relationship("MedicalDocument", back_populates="pap_smear_reports")
