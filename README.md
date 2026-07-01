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
4. **Quality validation** is skipped for text PDFs and applied to scanned PDFs / image uploads only. Scanned PDFs are assessed **page-by-page** (`assess_many`); the document-level summary follows the worst page conservatively (status/fixability from the worst page, average score reported) and per-page details are stored in the quality-check `issues`.
5. **Preprocessing happens only when needed.** Quality has two separate flags: `is_acceptable` (good enough as-is) and `is_fixable` (preprocessing can plausibly help). `good_quality` is never preprocessed; `needs_preprocessing` and `poor_quality`-but-`is_fixable` are enhanced and re-assessed (continuing only if quality actually improves); `poor_quality` and not `is_fixable` stops at `poor_quality`. Rendering a scanned PDF to page images for OCR is *rendering*, not image enhancement.
6. **Preprocessing** never overwrites originals. Enhanced pages are saved under `storage/processed/{document_id}/page_001.png`; rendered-for-OCR pages under `storage/rendered/{document_id}/page_001.png`.
7. **OCR runs once per upload** for images/scanned PDFs: a single OCR pass produces the text used for *both* relevance validation and extraction (no duplicated OCR work or duplicated `ocr_pages` rows). Full text and page-level OCR rows are stored in `ocr_pages`.
8. **Classification and extraction** run on OCR/PDF text, including Persian/English lab reports. Persian/Arabic-Indic digits (`۰۱۲۳…`, `٠١٢٣…`) are normalized to ASCII before parsing.
9. **Common fields include line-level evidence** — each field carries `value`, `confidence`, `source_text`, `source_line_index` (and `calendar` for dates). The national-ID evidence is masked unless `ALLOW_RAW_NATIONAL_ID=true`.
10. **Human verification** (`verification_status`) is tracked separately from pipeline state (`validation_status`).

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

## Evaluating on real samples

Real extraction quality must be measured on real documents, not synthetic ones. Two offline scripts help, and neither requires running the FastAPI server — they use the same DB/session/services as the app.

### 1. Run the pipeline over a folder

```bash
python scripts/evaluate_samples.py \
  --input-dir samples/raw \
  --output-dir samples/output \
  --reset-db --limit 20
```

Supported inputs: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`. For each file it writes:

- `samples/output/json/{name}.json` — the full API-shaped response;
- `samples/output/ocr/{name}.txt` — the extracted OCR/PDF text;
- a row in `samples/output/summary.csv`.

Flags: `--reset-db` (drop+recreate tables and clear the output dir), `--limit N` (quick testing), `--copy-files true|false` (copy inputs into `storage/originals`, the default, vs. reference them in place). Originals are never modified.

> Point `DATABASE_URL`/`STORAGE_DIR` at scratch locations if you don't want to touch your dev database, e.g. `DATABASE_URL=sqlite:///./eval.db STORAGE_DIR=eval_storage python scripts/evaluate_samples.py ...`.

### 2. Compare against manual annotations

Fill in `samples/annotation_template.csv` (one row per file; leave a column blank to skip that metric), then:

```bash
python scripts/compare_annotations.py \
  --summary samples/output/summary.csv \
  --annotations samples/annotation_template.csv \
  --output samples/output/metrics.json
```

It reports `document_type_accuracy`, `patient_name_found_accuracy`, `date_found_accuracy`, `lab_result_count_exact_match`, `average_extraction_confidence`, `needs_review_rate`, and `rejection_rate` over the annotated rows.

## Development reset

SQLite schema changes are not yet managed by Alembic, so during development you may need to delete the database and stored files after a model change:

```bash
rm -f medical_documents.db
rm -rf storage/
```

## Current limitations

- OCR quality depends on locally installed OCR engines and source image quality. Real quality must be measured on real samples (see [Evaluating on real samples](#evaluating-on-real-samples)).
- PaddleOCR support is optional and used only when installed and enabled; it cannot combine English+Persian in one run.
- Lab/common-field extraction is **regex/dictionary based (MVP only)**; it does not hallucinate missing values and sends uncertain rows/documents to review.
- Layout-aware lab extraction is still limited: Tavo-style column-major tables are supported for common analytes, but not every vendor/table format is recognized.
- No Celery/background/async worker yet; the pipeline runs synchronously on upload.
- No Alembic migration layer yet; SQLite + `create_all` is used for the MVP, so schema changes require a development reset (see above).
- No human review UI yet; review is via the API endpoints only.

## Running the API

```bash
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest -q
```


## Evaluation and Tavo lab OCR notes

Recent fixes target the real sample evaluation workflow:

- `.jpg` inputs are now evaluated and validated as `image/jpeg`; `image/jpg` is tolerated as an upload alias for compatibility.
- Tavo lab PDFs with column-major OCR/table text are supported for common biochemistry, CBC, thyroid, and vitamin-D analytes.
- Tavo Persian patient header lines such as `خانوادگی- آقای نام- دکتر43 : سن` are parsed as patient name, sex, and age; `دکتر43` is treated as age context, not a doctor name.
- Guideline/reference comments such as `High >400 l`, `Desirable <200`, and `Average risk : 4.4 - 7.1` are suppressed as standalone lab results.
- Known limitation: not every lab vendor/table layout is supported. Uncertain extraction should remain `needs_review` rather than inventing values.

Run evaluation on real files with:

```bash
python scripts/evaluate_samples.py --input-dir samples/raw --output-dir samples/output --reset-db
```

For non-SQLite databases, destructive reset requires explicit confirmation:

```bash
python scripts/evaluate_samples.py --input-dir samples/raw --output-dir samples/output --reset-db --yes
```

After evaluation, inspect:

- `samples/output/summary.csv`
- `samples/output/json/*.json`
- `samples/output/ocr/*.txt`

## Stateless extraction API (primary path)

This service is now intended to be a **stateless extraction API**. The backend/dev team owns upload orchestration, permanent file storage, databases, authentication, saved extraction results, review UI, patient-profile integration, production buckets, and migrations. This service reads a temporary input, performs document analysis/OCR/extraction, and returns JSON only.

### Endpoints

- `POST /extract/file` — multipart upload. The uploaded file is copied to a temporary file, processed, and deleted automatically.
- `POST /extract` — JSON input with exactly one of `file_path`, `file_url`, or `base64_content`.
- `GET /extract/health` — health check for the stateless extraction API.

Example JSON request:

```json
{
  "request_id": "req-123",
  "document_id": "backend-doc-456",
  "file_name": "report.pdf",
  "mime_type": "application/pdf",
  "file_path": "/tmp/backend-upload/report.pdf",
  "debug": false
}
```

The response includes `request_id`, `document_id`, `status`, `document_type`, `confidence`, `quality`, `ocr`, `common_fields`, `extracted_data`, `errors`, and `warnings`. Raw national IDs are not exposed by default; only hashes are returned unless `ALLOW_RAW_NATIONAL_ID=true` is configured.

### Standard statuses and codes

Statuses: `success`, `low_confidence`, `unsupported_file`, `invalid_file`, `poor_quality`, `ocr_failed`, `unrelated_document`, `extraction_failed`.

Error codes include: `UNSUPPORTED_FILE_TYPE`, `INVALID_MIME_TYPE`, `FILE_READ_ERROR`, `PDF_PASSWORD_PROTECTED`, `POOR_IMAGE_QUALITY`, `OCR_ENGINE_MISSING`, `OCR_FAILED`, `OCR_EMPTY_TEXT`, `UNRELATED_DOCUMENT`, `CLASSIFICATION_FAILED`, `EXTRACTION_FAILED`, `LOW_CONFIDENCE`, `URL_DOWNLOAD_FAILED`, and `BASE64_DECODE_FAILED`.

Warning codes include: `LOW_OCR_CONFIDENCE`, `MISSING_PATIENT_NAME`, `MISSING_REPORT_DATE`, `MISSING_LAB_ROWS`, `POSSIBLE_TABLE_LAYOUT_ISSUE`, `LOW_EXTRACTION_CONFIDENCE`, `PADDLEOCR_FALLBACK_TO_TESSERACT`, `QUALITY_PREPROCESSING_APPLIED`, and `INFERRED_REPORT_NAME`.

### Evaluation

Run the stateless evaluation harness without any database setup:

```bash
python scripts/evaluate_samples.py \
  --input-dir samples/raw \
  --output-dir samples/output \
  --limit 20 \
  --debug
```

It writes one JSON result per document, one OCR text file per document when `--debug` is enabled, and `summary.csv`.

### Legacy routes

The previous `/documents/*` and review routes remain for backward compatibility and internal comparison, but they are database-backed legacy routes. New integrations should use `/extract/file` or `/extract`.

### Current limitations

- `file_url` currently returns `URL_DOWNLOAD_FAILED` instead of downloading remote content.
- Image OCR quality depends on the locally installed OCR backend and language packs.
- Debug responses can include OCR text and parser details; keep `debug=false` for normal backend handoff.
