from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import MedicalDocument
from app.schemas.review import RejectRequest, ReviewResponse
from app.services.review_service import ReviewService
router=APIRouter(prefix='/documents/{document_id}/review', tags=['review'])
def getdoc(db,id):
    d=db.get(MedicalDocument,id)
    if not d: raise HTTPException(404,'Document not found')
    return d
@router.post('/verify', response_model=ReviewResponse)
def verify(document_id:int, db:Session=Depends(get_db)):
    d=ReviewService().verify(db,getdoc(db,document_id)); return ReviewResponse(document_id=d.id,status=d.validation_status,verification_status=d.verification_status,rejection_reason=d.rejection_reason)
@router.post('/reject', response_model=ReviewResponse)
def reject(document_id:int, req:RejectRequest, db:Session=Depends(get_db)):
    d=ReviewService().reject(db,getdoc(db,document_id),req.reason); return ReviewResponse(document_id=d.id,status=d.validation_status,verification_status=d.verification_status,rejection_reason=d.rejection_reason)
@router.post('/needs-review', response_model=ReviewResponse)
def needs_review(document_id:int, db:Session=Depends(get_db)):
    d=ReviewService().needs_review(db,getdoc(db,document_id)); return ReviewResponse(document_id=d.id,status=d.validation_status,verification_status=d.verification_status,rejection_reason=d.rejection_reason)
