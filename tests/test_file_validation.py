from app.services.file_validation_service import FileValidationService

def test_unsupported_file_type_returns_unsupported(tmp_path):
    p=tmp_path/'note.txt'; p.write_text('hello')
    r=FileValidationService().validate(str(p),'note.txt','text/plain')
    assert r.status=='unsupported_file_type'
