from app.models.document import MedicalDocument
from app.models.review import ReviewTask
from app.services.review_service import ReviewService


def _processed_doc(db):
    doc=MedicalDocument(
        original_file_path='x', original_file_name='x.pdf', original_file_type='application/pdf',
        file_size_bytes=1, file_hash='h', validation_status='processed', verification_status='needs_review',
    )
    db.add(doc); db.commit(); db.refresh(doc)
    return doc


def test_verify_keeps_validation_status_and_closes_tasks(db_session):
    doc=_processed_doc(db_session)
    db_session.add(ReviewTask(document_id=doc.id, reason='r', status='open')); db_session.commit()
    ReviewService().verify(db_session, doc)
    assert doc.validation_status=='processed'
    assert doc.verification_status=='verified'
    open_tasks=db_session.query(ReviewTask).filter_by(document_id=doc.id, status='open').count()
    assert open_tasks==0


def test_reject_keeps_validation_status(db_session):
    doc=_processed_doc(db_session)
    ReviewService().reject(db_session, doc, 'not readable')
    assert doc.validation_status=='processed'
    assert doc.verification_status=='rejected'
    assert doc.rejection_reason=='not readable'


def test_needs_review_keeps_validation_status_and_creates_one_task(db_session):
    doc=_processed_doc(db_session)
    doc.verification_status='unverified'; db_session.commit()
    ReviewService().needs_review(db_session, doc)
    ReviewService().needs_review(db_session, doc)  # second call must not duplicate the open task
    assert doc.validation_status=='processed'
    assert doc.verification_status=='needs_review'
    open_tasks=db_session.query(ReviewTask).filter_by(document_id=doc.id, status='open').count()
    assert open_tasks==1


def test_verify_sets_validation_only_when_empty(db_session):
    doc=MedicalDocument(original_file_path='x', original_file_name='x.pdf', original_file_type='application/pdf',
                        file_size_bytes=1, file_hash='h2', validation_status='', verification_status='unverified')
    db_session.add(doc); db_session.commit(); db_session.refresh(doc)
    ReviewService().verify(db_session, doc)
    assert doc.validation_status=='processed'
    assert doc.verification_status=='verified'
