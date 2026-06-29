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

## MVP document-processing pipeline

The backend now distinguishes text PDFs, scanned PDFs, and image uploads before validation decisions are made:

1. **File validation** checks upload type and safety.
2. **Document analysis** identifies `pdf` vs `image`, text-layer length, page count, and whether rendering is required.
3. **Relevance validation** uses real extracted text where possible:
   - text PDFs use embedded PDF text;
   - scanned PDFs render/preprocess the first pages and run light OCR;
   - image uploads run quality assessment, preprocessing when fixable, and OCR before relevance checks.
4. **Quality validation** is skipped for text PDFs and applied to scanned/image uploads only.
5. **Preprocessing** never overwrites originals. Processed pages are saved under `storage/processed/{document_id}/page_001.png` etc.
6. **OCR** stores full text and page-level OCR rows in `ocr_pages`.
7. **Classification and extraction** run on OCR/PDF text, including Persian/English lab reports.
8. **Human verification** is tracked separately from pipeline status.

## Text PDFs vs scanned PDFs

- Text PDFs with an embedded text layer above `PDF_TEXT_THRESHOLD` are marked `text_pdf` and go directly to PDF text extraction.
- PDFs with little or no embedded text are marked `scanned_pdf`, rendered to images, preprocessed, quality checked, and OCRed page-by-page.
- `MAX_PREPROCESS_PAGES` defaults to `5` for scanned PDF preprocessing.

## Image upload relevance behavior

Images are no longer rejected as unrelated based only on file name. The service attempts image quality assessment, fixable preprocessing, and OCR. If OCR cannot run because an engine is unavailable, the pipeline reports `ocr_failed` with a clear Tesseract/PaddleOCR installation message instead of pretending the document is unrelated.

## OCR backends

Default settings:

```env
OCR_BACKEND=tesseract
ENABLE_PADDLEOCR=false
```

- **Tesseract** is the default image OCR backend via `pytesseract`.
- **PaddleOCR** is optional. Set `ENABLE_PADDLEOCR=true` and install PaddleOCR separately if you want to try it. It is not a required dependency because it is heavy.
- Text PDFs use PyMuPDF embedded text extraction (`pdf_text`) before image OCR.

### Install Tesseract

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-fas
```

macOS:

```bash
brew install tesseract tesseract-lang
```

## National ID privacy

Iranian national IDs are extracted when visible, but raw values are **not** exposed or saved by default. The `national_id_hash` field stores a SHA-256 hash. Raw national ID storage is only allowed for development when:

```env
ALLOW_RAW_NATIONAL_ID=true
```

## Status definitions

`validation_status` describes pipeline state:

- `uploaded`
- `invalid_file`
- `unsupported_file_type`
- `unrelated_document`
- `poor_quality`
- `ready_for_ocr`
- `ocr_processing`
- `ocr_failed`
- `classification_processing`
- `extraction_processing`
- `extraction_failed`
- `processed`
- `duplicate_document`

`verification_status` describes human review state:

- `unverified`
- `needs_review`
- `verified`
- `rejected`

Successful automated extraction now sets `validation_status=processed`. Low-confidence documents use `verification_status=needs_review`; strong but unreviewed documents use `verification_status=unverified`.

## Duplicate uploads

The upload flow detects an existing `file_hash`. Duplicate uploads are not blocked by default; the response includes the warning `duplicate_file_hash_detected`.

## Current limitations

- OCR quality depends on locally installed OCR engines and source image quality.
- PaddleOCR support is optional and currently used only when installed and enabled.
- Lab extraction is regex/dictionary based; it does not hallucinate missing values and sends uncertain rows/documents to review.
- No Celery/background queue or Alembic migration layer has been added; SQLite and `create_all` remain supported for the MVP.

## Running the API

```bash
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest -q
```
