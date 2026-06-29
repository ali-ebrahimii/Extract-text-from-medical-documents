from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import MedicalDocument
from app.services.storage_service import StorageService
from app.services.pipeline_service import PipelineService
from app.schemas.document import DocumentUploadResponse, DocumentListItem, DocumentDetail
router=APIRouter(prefix='/documents', tags=['documents'])
def extracted(doc):
    return {'patients':[{'patient_name':p.patient_name,'patient_name_confidence':p.patient_name_confidence,'national_id_confidence':p.national_id_confidence} for p in doc.patients], 'lab_results':[{'test_name_raw':r.test_name_raw,'test_name_standard':r.test_name_standard,'result_value':r.result_value,'unit':r.unit,'reference_range':r.reference_range,'confidence':r.confidence,'raw_source_text':r.raw_row_text} for r in doc.lab_results], 'pap_smear_reports':[{'specimen_adequacy':r.specimen_adequacy,'interpretation_result':r.interpretation_result,'full_narrative_report':r.full_narrative_report,'confidence':r.confidence} for r in doc.pap_smear_reports], 'radiology_reports':[{'imaging_modality':r.imaging_modality,'body_part_or_exam_name':r.body_part_or_exam_name,'findings':r.findings,'impression_conclusion':r.impression_conclusion,'confidence':r.confidence} for r in doc.radiology_reports]}
@router.post('/upload', response_model=DocumentUploadResponse)
def upload(file: UploadFile=File(...), db: Session=Depends(get_db)):
    path,size,h=StorageService().save_upload(file)
    doc=MedicalDocument(original_file_path=path, original_file_name=file.filename or 'upload', original_file_type=file.content_type or '', file_size_bytes=size, file_hash=h, validation_status='uploaded', verification_status='needs_review')
    db.add(doc); db.commit(); db.refresh(doc)
    doc=PipelineService().process_document(db, doc.id)
    return DocumentUploadResponse(document_id=doc.id,status=doc.validation_status,verification_status=doc.verification_status,rejection_reason=doc.rejection_reason,quality_score_before=doc.quality_score_before,quality_score_after=doc.quality_score_after,relevance_score=doc.relevance_score,document_type=doc.document_type,extraction_confidence=doc.extraction_confidence,next_action='manual_review' if doc.verification_status=='needs_review' else 'none',extracted_data=extracted(doc))
@router.get('', response_model=list[DocumentListItem])
def list_docs(status:str|None=None, document_type:str|None=None, verification_status:str|None=None, db:Session=Depends(get_db)):
    q=db.query(MedicalDocument)
    if status: q=q.filter(MedicalDocument.validation_status==status)
    if document_type: q=q.filter(MedicalDocument.document_type==document_type)
    if verification_status: q=q.filter(MedicalDocument.verification_status==verification_status)
    return q.order_by(MedicalDocument.created_at.desc()).all()
@router.get('/{document_id}', response_model=DocumentDetail)
def get_doc(document_id:int, db:Session=Depends(get_db)):
    doc=db.get(MedicalDocument, document_id)
    if not doc: raise HTTPException(404,'Document not found')
    return DocumentDetail.model_validate(doc).model_copy(update={'extracted_data':extracted(doc)})
