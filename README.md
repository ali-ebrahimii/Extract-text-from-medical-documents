# Medical Document Extraction MVP

FastAPI backend for receiving patient-uploaded PDF/image medical documents, validating files, checking medical relevance and quality, preprocessing fixable images, extracting text, classifying document type, extracting structured fields, scoring confidence, and creating review-ready records.

## Pipeline

```text
Upload -> Security/File Validation -> Medical Relevance -> Initial Quality -> Preprocess if needed
-> Post Quality -> OCR/Text Extraction -> Classification -> Common Extraction
-> Document-Specific Extraction -> Normalization -> Confidence -> Human Review -> Verified Save
```

Original uploads are always preserved under `storage/originals`. Preprocessed derivatives are saved separately under `storage/processed` and used for OCR when available.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## API examples

```bash
curl http://localhost:8000/health
curl -F "file=@sample.pdf" http://localhost:8000/documents/upload
curl http://localhost:8000/documents/1
curl "http://localhost:8000/documents?status=needs_review&document_type=lab"
curl -X POST http://localhost:8000/documents/1/review/verify
curl -X POST http://localhost:8000/documents/1/review/reject -H 'Content-Type: application/json' -d '{"reason":"not readable"}'
curl -X POST http://localhost:8000/documents/1/review/needs-review
```

## Statuses

`uploaded`, `security_rejected`, `unsupported_file_type`, `invalid_file`, `unrelated_document`, `quality_check_failed`, `needs_preprocessing`, `preprocessing`, `preprocessing_failed`, `poor_quality`, `ready_for_ocr`, `ocr_processing`, `ocr_failed`, `classification_processing`, `extraction_processing`, `extraction_failed`, `needs_review`, `verified`, `rejected`.

## Environment variables

- `DATABASE_URL`: SQLAlchemy URL; SQLite by default and PostgreSQL-ready.
- `STORAGE_DIR`: local file storage root.
- `MAX_UPLOAD_MB`: maximum upload size.

## Current limitations

- OCR for images depends on system Tesseract availability.
- PDF scanned-page rendering is MVP-only and processes the first page for preprocessing.
- Rule-based extraction and classification are intentionally conservative.
- Human verification is required before final `verified` status.

## TODO roadmap

- Background jobs for long-running pipeline steps.
- PostgreSQL migrations with Alembic.
- Object storage support.
- Better multilingual OCR and Persian extraction rules.
- Human review UI and audit logging.
