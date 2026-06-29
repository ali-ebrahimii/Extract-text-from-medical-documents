from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import MedicalDocument
from app.models.preprocessing import DocumentPreprocessing
from app.models.quality import DocumentQualityCheck, DocumentRelevanceCheck
from app.models.ocr_page import OCRPage
from app.services.storage_service import StorageService
from app.services.pipeline_service import PipelineService
from app.services.common_field_extractor import CommonFieldExtractor
from app.schemas.document import DocumentUploadResponse, DocumentListItem, DocumentDetail
router=APIRouter(prefix='/documents', tags=['documents'])

def extracted(doc):
    return {'patients':[{'patient_name':p.patient_name,'patient_name_confidence':p.patient_name_confidence,'national_id':{'value':None,'hash':p.national_id_hash,'confidence':p.national_id_confidence},'age':p.age,'sex':p.sex} for p in doc.patients], 'lab_results':[{'category':r.category,'test_name_raw':r.test_name_raw,'test_name_standard':r.test_name_standard,'result_value':r.result_value,'result_numeric':r.result_numeric,'unit':r.unit,'method':r.method,'reference_range':r.reference_range,'abnormal_flag':r.abnormal_flag,'sample_type':r.sample_type,'page_number':r.page_number,'confidence':r.confidence,'raw_row_text':r.raw_row_text} for r in doc.lab_results], 'pap_smear_reports':[{'specimen_adequacy':r.specimen_adequacy,'interpretation_result':r.interpretation_result,'full_narrative_report':r.full_narrative_report,'confidence':r.confidence} for r in doc.pap_smear_reports], 'radiology_reports':[{'imaging_modality':r.imaging_modality,'body_part_or_exam_name':r.body_part_or_exam_name,'findings':r.findings,'impression_conclusion':r.impression_conclusion,'confidence':r.confidence} for r in doc.radiology_reports]}

def rich_doc(doc, db):
    prep=db.query(DocumentPreprocessing).filter_by(document_id=doc.id).order_by(DocumentPreprocessing.id.desc()).first()
    qual=db.query(DocumentQualityCheck).filter_by(document_id=doc.id).order_by(DocumentQualityCheck.id.desc()).first()
    rel=db.query(DocumentRelevanceCheck).filter_by(document_id=doc.id).order_by(DocumentRelevanceCheck.id.desc()).first()
    pages=db.query(OCRPage).filter_by(document_id=doc.id).order_by(OCRPage.page_number).all()
    common={}
    if doc.ocr_text: common=CommonFieldExtractor().extract_structured(doc.ocr_text)
    if doc.document_type=="lab" and doc.test_or_report_name and not ((common.get("test_or_report_name") or {}).get("value")):
        common["test_or_report_name"]={"value":doc.test_or_report_name,"confidence":0.5,"source_text":None,"source_line_index":None,"inferred":True}
    return {"document_id":doc.id,"status":doc.validation_status,"validation_status":doc.validation_status,"verification_status":doc.verification_status,"document_type":doc.document_type,"document_type_confidence":doc.document_type_confidence,"rejection_reason":doc.rejection_reason,"next_action":"manual_review" if doc.verification_status=='needs_review' else ('fix_and_reupload' if doc.validation_status in ['poor_quality','ocr_failed','invalid_file'] else 'none'),"original_file":{"name":doc.original_file_name,"path":doc.original_file_path,"content_type":doc.original_file_type,"size_bytes":doc.file_size_bytes,"sha256":doc.file_hash},"preprocessing":None if not prep else {"required":prep.preprocessing_required,"applied":prep.preprocessing_applied,"status":prep.preprocessing_status,"steps":prep.preprocessing_steps,"output_path":prep.preprocessed_page_path,"output_paths":prep.preprocessed_page_paths,"error":prep.preprocessing_error},"quality":None if not qual else {"status":"good_quality" if qual.is_acceptable else "poor_quality","overall_quality_score":qual.overall_quality_score,"issues":(qual.issues or {}).get("issues", qual.issues) if isinstance(qual.issues,dict) else qual.issues,"details":qual.issues,"is_acceptable":qual.is_acceptable},"relevance":None if not rel else {"is_medical_document":rel.is_medical_document,"relevance_score":rel.relevance_score,"detected_keywords":rel.detected_keywords,"reason":rel.rejection_reason},"ocr":{"success":bool(doc.ocr_text),"confidence":doc.ocr_confidence,"text_length":len(doc.ocr_text or ''),"pages":[{"page_number":p.page_number,"source_path":p.source_path,"confidence":p.ocr_confidence,"text_length":len(p.ocr_text or '')} for p in pages]},"common_fields":common,"extracted_data":extracted(doc),"warnings":doc.warnings or [],"extraction_confidence":doc.extraction_confidence,"quality_score_before":doc.quality_score_before,"quality_score_after":doc.quality_score_after,"relevance_score":doc.relevance_score}

@router.post('/upload', response_model=DocumentUploadResponse)
def upload(file: UploadFile=File(...), db: Session=Depends(get_db)):
    path,size,h=StorageService().save_upload(file)
    doc=MedicalDocument(original_file_path=path, original_file_name=file.filename or 'upload', original_file_type=file.content_type or '', file_size_bytes=size, file_hash=h, validation_status='uploaded', verification_status='unverified')
    db.add(doc); db.commit(); db.refresh(doc)
    doc=PipelineService().process_document(db, doc.id)
    return rich_doc(doc, db)
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
    return rich_doc(doc, db)
