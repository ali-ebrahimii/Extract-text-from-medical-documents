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

The system tracks two independent axes — see [Status definitions](#status-definitions) below. `validation_status` is the pipeline state (`uploaded` … `processed` / `duplicate_document`); `verification_status` is the human-review state (`unverified`, `needs_review`, `verified`, `rejected`).

## Environment variables

- `DATABASE_URL`: SQLAlchemy URL; SQLite by default and PostgreSQL-ready.
- `STORAGE_DIR`: local file storage root.
- `MAX_UPLOAD_MB`: maximum upload size.
- `PDF_TEXT_THRESHOLD`: embedded-text length above which a PDF is treated as a text PDF.
- `MAX_PREPROCESS_PAGES`: max pages rendered/preprocessed for scanned PDFs (default `5`).
- `OCR_BACKEND`: `tesseract` (default), `paddleocr`, or `auto`.
- `ENABLE_PADDLEOCR`: opt PaddleOCR in (default `false`).
- `TESSERACT_LANG`: Tesseract language(s), e.g. `eng+fas` (default).
- `PADDLEOCR_LANG`: PaddleOCR language, e.g. `en` (default).
- `ALLOW_RAW_NATIONAL_ID`: store/expose raw national IDs (default `false`).
- `BLOCK_DUPLICATE_UPLOADS`: block duplicate file-hash uploads (default `false`).

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
   - scanned PDFs are rendered to page images (up to `MAX_PREPROCESS_PAGES`) and run light OCR;
   - image uploads run quality assessment, preprocessing only when needed, and OCR before relevance checks.
   - Image relevance is OCR-based, never filename-only.
4. **Quality validation** is skipped for text PDFs and applied to scanned PDFs / image uploads only.
5. **Preprocessing happens only when needed.** Good-quality input is never preprocessed (preprocessing can damage already-clean images). Rendering a scanned PDF to page images for OCR is treated as *rendering*, not image-enhancement preprocessing.
6. **Preprocessing** never overwrites originals. Enhanced pages are saved under `storage/processed/{document_id}/page_001.png`; rendered-for-OCR pages under `storage/rendered/{document_id}/page_001.png`.
7. **OCR** stores full text and page-level OCR rows in `ocr_pages`.
8. **Classification and extraction** run on OCR/PDF text, including Persian/English lab reports.
9. **Human verification** (`verification_status`) is tracked separately from pipeline state (`validation_status`).

## Text PDFs vs scanned PDFs

- Text PDFs with an embedded text layer above `PDF_TEXT_THRESHOLD` are marked `text_pdf`, skip image quality/preprocessing, and go directly to PDF text extraction.
- PDFs with little or no embedded text are marked `scanned_pdf`, quality checked, rendered (and enhanced only if quality is not good), and OCRed page-by-page.
- `MAX_PREPROCESS_PAGES` (default `5`) caps how many pages of a scanned PDF are rendered/preprocessed. If the PDF has fewer pages, only the available pages are processed; the value is never hardcoded in the pipeline.

## Image upload relevance behavior

Images are no longer rejected as unrelated based only on file name. The service attempts image quality assessment, fixable preprocessing, and OCR. If OCR cannot run because an engine is unavailable, the pipeline reports `ocr_failed` with a clear Tesseract/PaddleOCR installation message instead of pretending the document is unrelated.

## OCR backends

Default settings:

```env
OCR_BACKEND=tesseract
ENABLE_PADDLEOCR=false
TESSERACT_LANG=eng+fas
PADDLEOCR_LANG=en
```

- `OCR_BACKEND` selects the backend: `tesseract` (default), `paddleocr`, or `auto`.
  - `tesseract`: use `pytesseract` with `lang=TESSERACT_LANG`.
  - `paddleocr`: try PaddleOCR with `lang=PADDLEOCR_LANG`; if PaddleOCR is unavailable it falls back to Tesseract.
  - `auto`: try PaddleOCR when `ENABLE_PADDLEOCR=true`, otherwise Tesseract.
- `ENABLE_PADDLEOCR=true` also opts PaddleOCR in when the backend is `tesseract`/`auto`.
- **Tesseract** is the default image OCR backend via `pytesseract`.
- **PaddleOCR** is optional and heavy; it is not a required dependency. Install it separately to enable it.
- Text PDFs use PyMuPDF embedded text extraction before any image OCR.
- If no OCR engine is available the pipeline returns a stable `ocr_failed` result with a clear install message instead of crashing.

### Tesseract language data (`TESSERACT_LANG=eng+fas`)

`TESSERACT_LANG=eng+fas` runs Tesseract with both English and Persian models, which suits mixed Persian/English reports. You must install the Persian (`fas`) language data for this to work.

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-fas
```

macOS (Homebrew bundles all language packs, including `fas`):

```bash
brew install tesseract tesseract-lang
```

Verify Persian is installed:

```bash
tesseract --list-langs   # should include "fas" and "eng"
```

### PaddleOCR language configuration

PaddleOCR uses a single language code per run, configured via `PADDLEOCR_LANG` (e.g. `en`, `ar`, `ch`). PaddleOCR has no combined English+Persian model, so for Persian-heavy documents prefer Tesseract with `eng+fas`.

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

The upload flow detects an existing `file_hash`.

- `BLOCK_DUPLICATE_UPLOADS=false` (default): the upload is allowed and the response includes the warning `duplicate_file_hash_detected`.
- `BLOCK_DUPLICATE_UPLOADS=true`: the document is marked `validation_status=duplicate_document`, the extraction pipeline is skipped, and the warnings include `existing_document_id=<id>` pointing at the original.

## Development reset

SQLite schema changes are not yet managed by Alembic, so during development you may need to delete the database and stored files after a model change:

```bash
rm -f medical_documents.db
rm -rf storage/
```

## Current limitations

- OCR quality depends on locally installed OCR engines and source image quality.
- PaddleOCR support is optional and used only when installed and enabled; it cannot combine English+Persian in one run.
- Lab/common-field extraction is regex/dictionary based; it does not hallucinate missing values and sends uncertain rows/documents to review.
- No Celery/background queue has been added; the pipeline runs synchronously on upload.
- No Alembic migration layer yet; SQLite + `create_all` is used for the MVP, so schema changes require a development reset (see above).

## Running the API

```bash
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest -q
```
