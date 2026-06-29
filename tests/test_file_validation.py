from app.services.file_validation_service import FileValidationService

def test_unsupported_file_type_returns_unsupported(tmp_path):
    p=tmp_path/'note.txt'; p.write_text('hello')
    r=FileValidationService().validate(str(p),'note.txt','text/plain')
    assert r.status=='unsupported_file_type'


def test_jpg_and_jpeg_mime_aliases_validate(tmp_path):
    from PIL import Image
    for name,mime in [('a.jpg','image/jpg'),('b.jpeg','image/jpeg')]:
        p=tmp_path/name; Image.new('RGB',(10,10),'white').save(p)
        r=FileValidationService().validate(str(p),name,mime)
        assert r.is_valid


def test_unsupported_image_mime_fails(tmp_path):
    from PIL import Image
    p=tmp_path/'a.jpg'; Image.new('RGB',(10,10),'white').save(p)
    r=FileValidationService().validate(str(p),'a.jpg','image/gif')
    assert not r.is_valid and r.status=='invalid_file'
