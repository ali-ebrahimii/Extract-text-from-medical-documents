from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from app.models.document import Base
class LabResult(Base):
    __tablename__="lab_results"
    id=Column(Integer, primary_key=True); document_id=Column(Integer, ForeignKey("medical_documents.id"), index=True)
    category=Column(String); test_name_raw=Column(String); test_name_standard=Column(String); result_value=Column(String); result_numeric=Column(Float); unit=Column(String); reference_range=Column(String); abnormal_flag=Column(String); method=Column(String); sample_type=Column(String); confidence=Column(Float); page_number=Column(Integer); bbox=Column(JSON); raw_row_text=Column(Text); created_at=Column(DateTime, default=datetime.utcnow)
    document=relationship("MedicalDocument", back_populates="lab_results")
