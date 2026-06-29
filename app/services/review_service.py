from datetime import datetime

from sqlalchemy.orm import Session

from app.core.enums import VerificationStatus
from app.models.document import MedicalDocument
from app.models.review import ReviewTask


class ReviewService:
    """Human-review state transitions.

    This service only ever touches ``verification_status`` (the human review
    state). It must never overwrite ``validation_status`` (the pipeline state)
    with a verification value such as ``verified``/``rejected``/``needs_review``.
    """

    def _close_open_tasks(self, db: Session, doc: MedicalDocument) -> None:
        open_tasks = (
            db.query(ReviewTask)
            .filter(ReviewTask.document_id == doc.id, ReviewTask.status == "open")
            .all()
        )
        for task in open_tasks:
            task.status = "closed"
            task.reviewed_at = datetime.utcnow()

    def _has_open_task(self, db: Session, doc: MedicalDocument) -> bool:
        return (
            db.query(ReviewTask)
            .filter(ReviewTask.document_id == doc.id, ReviewTask.status == "open")
            .first()
            is not None
        )

    def verify(self, db: Session, doc: MedicalDocument) -> MedicalDocument:
        doc.verification_status = VerificationStatus.VERIFIED.value
        # Only set validation_status if it is empty/null; never overwrite it.
        if not doc.validation_status:
            doc.validation_status = VerificationStatus.VERIFIED.value
        self._close_open_tasks(db, doc)
        db.commit()
        db.refresh(doc)
        return doc

    def reject(self, db: Session, doc: MedicalDocument, reason: str | None) -> MedicalDocument:
        doc.verification_status = VerificationStatus.REJECTED.value
        doc.rejection_reason = reason
        self._close_open_tasks(db, doc)
        db.commit()
        db.refresh(doc)
        return doc

    def needs_review(
        self,
        db: Session,
        doc: MedicalDocument,
        reason: str = "Manual review requested",
        priority: int = 3,
    ) -> MedicalDocument:
        doc.verification_status = VerificationStatus.NEEDS_REVIEW.value
        if not self._has_open_task(db, doc):
            db.add(ReviewTask(document_id=doc.id, reason=reason, priority=priority, status="open"))
        db.commit()
        db.refresh(doc)
        return doc
