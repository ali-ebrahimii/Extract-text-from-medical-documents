from app.services.relevance_service import RelevanceService

def test_unrelated_text_file_returns_unrelated():
    r=RelevanceService().check('/tmp/missing.png','vacation_photo.png','mountain sunset family holiday')
    assert not r.is_medical_document
    assert r.relevance_score < .15
