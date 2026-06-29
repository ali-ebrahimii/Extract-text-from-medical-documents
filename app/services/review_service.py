from datetime import datetime
from app.core.enums import DocumentStatus
from app.models.review import ReviewTask
class ReviewService:
    def verify(self,db,doc): doc.verification_status=DocumentStatus.VERIFIED.value; doc.validation_status=DocumentStatus.VERIFIED.value; db.commit(); return doc
    def reject(self,db,doc,reason): doc.verification_status=DocumentStatus.REJECTED.value; doc.validation_status=DocumentStatus.REJECTED.value; doc.rejection_reason=reason; db.commit(); return doc
    def needs_review(self,db,doc,reason='Manual review requested',priority=3):
        doc.verification_status=DocumentStatus.NEEDS_REVIEW.value; doc.validation_status=DocumentStatus.NEEDS_REVIEW.value; db.add(ReviewTask(document_id=doc.id,reason=reason,priority=priority,status='open')); db.commit(); return doc
