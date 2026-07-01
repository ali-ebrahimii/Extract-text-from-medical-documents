from app.models.document import MedicalDocument
from app.models.patient import DocumentPatient
from app.models.quality import DocumentQualityCheck, DocumentRelevanceCheck
from app.models.preprocessing import DocumentPreprocessing
from app.models.lab_result import LabResult
from app.models.pap_smear import PapSmearReport
from app.models.radiology import RadiologyReport
from app.models.review import ReviewTask
from app.models.ocr_page import OCRPage
from app.db.session import engine
from sqlalchemy.orm import declarative_base
# Base is imported from document module for all models.
from app.models.document import Base

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
