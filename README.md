# Stateless Medical Document Extraction Service

This repository exposes a **stateless medical document extraction API**. It receives temporary file input, analyzes the document, runs OCR when needed, extracts structured medical fields, and returns JSON results.

It **does not own** database state, permanent file storage, authentication, upload orchestration, review UI, saved extraction results, or patient-profile integration. Those responsibilities belong to the backend/dev team that calls this service.

## Active responsibilities

- Stateless extraction API
- Document analysis and medical relevance checks
- OCR for PDFs/images
- Quality assessment and preprocessing for fixable inputs
- Document classification
- Structured medical extraction for common fields, labs, Pap smear reports, and radiology reports
- Confidence scoring
- Standardized error and warning codes
- Offline stateless evaluation scripts

## API

Run locally:

```bash
uvicorn app.main:app --reload
```

### Health

```bash
curl http://localhost:8000/extract/health
```

Response:

```json
{"status":"ok","service":"stateless-extraction"}
```

### `POST /extract/file`

Use multipart upload for a temporary file. The service does not persist the upload.

```bash
curl -F "file=@sample.pdf" \
  -F "document_id=optional-external-id" \
  -F "debug=false" \
  http://localhost:8000/extract/file
```

### `POST /extract`

Use JSON with one of `file_path`, `base64_content`, or `file_url`. `file_url` is reserved and returns `URL_DOWNLOAD_FAILED` in this MVP.

```bash
curl -X POST http://localhost:8000/extract \
  -H 'Content-Type: application/json' \
  -d '{
    "document_id":"optional-external-id",
    "file_path":"/tmp/sample.pdf",
    "file_name":"sample.pdf",
    "mime_type":"application/pdf",
    "debug":false
  }'
```

Base64 example:

```json
{
  "file_name": "sample.pdf",
  "mime_type": "application/pdf",
  "base64_content": "JVBERi0x..."
}
```

## Response shape

Successful or low-confidence extraction returns JSON like:

```json
{
  "request_id": "uuid",
  "document_id": "optional-external-id",
  "status": "success",
  "document_type": "lab",
  "confidence": 0.88,
  "quality": {"overall_quality_score": 0.9},
  "ocr": {"success": true, "confidence": 0.95, "text_length": 1200},
  "common_fields": {"patient_name": {"value": "..."}},
  "extracted_data": {"lab_results": []},
  "errors": [],
  "warnings": []
}
```

## Statuses

- `success` — extraction completed with acceptable confidence.
- `low_confidence` — extraction completed but confidence is below threshold.
- `unsupported_file` — extension or type is unsupported.
- `invalid_file` — file is missing, empty, unreadable, password-protected, or MIME-invalid.
- `poor_quality` — input quality is too poor to process.
- `ocr_failed` — OCR failed or returned no usable text.
- `unrelated_document` — document does not appear medically relevant.
- `extraction_failed` — unexpected extraction failure.

## Error codes

Common error codes include:

- `UNSUPPORTED_FILE_TYPE`
- `INVALID_MIME_TYPE`
- `PDF_PASSWORD_PROTECTED`
- `FILE_READ_ERROR`
- `BASE64_DECODE_FAILED`
- `URL_DOWNLOAD_FAILED`
- `POOR_IMAGE_QUALITY`
- `OCR_ENGINE_MISSING`
- `OCR_EMPTY_TEXT`
- `OCR_FAILED`
- `UNRELATED_DOCUMENT`
- `EXTRACTION_FAILED`

## Warning codes

Common warning codes include:

- `QUALITY_PREPROCESSING_APPLIED`
- `POSSIBLE_TABLE_LAYOUT_ISSUE`
- `INFERRED_REPORT_NAME`
- `MISSING_LAB_ROWS`
- `MISSING_PATIENT_NAME`
- `MISSING_REPORT_DATE`
- `LOW_EXTRACTION_CONFIDENCE`

## OCR requirements

The default OCR backend is Tesseract. Install the Tesseract binary and language data needed by your deployment, then configure:

```env
OCR_BACKEND=tesseract
TESSERACT_LANG=eng+fas
```

Optional PaddleOCR settings remain available for environments that install and enable PaddleOCR:

```env
OCR_BACKEND=paddleocr
ENABLE_PADDLEOCR=true
PADDLEOCR_LANG=en
```

## Configuration

See `.env.example`. Stateless configuration does not require `DATABASE_URL`, `STORAGE_DIR`, migrations, or duplicate-upload controls.

Useful settings:

- `MAX_UPLOAD_MB`
- `PDF_TEXT_THRESHOLD`
- `MAX_PREPROCESS_PAGES`
- `OCR_BACKEND`
- `TESSERACT_LANG`
- `ALLOW_RAW_NATIONAL_ID`
- `DEBUG_OUTPUT_DIR`
- `DEBUG_SAVE_INTERMEDIATE_FILES`

## Offline evaluation

Run the stateless evaluator directly against local samples:

```bash
python scripts/evaluate_samples.py --input-dir samples/raw --output-dir samples/output --debug
```

Outputs:

- `samples/output/json/*.json` — full extraction responses.
- `samples/output/ocr/*.txt` — OCR text when `--debug` is enabled; empty files may be written otherwise.
- `samples/output/summary.csv` — stateless summary columns for metrics.

Compare summary rows to manual annotations:

```bash
python scripts/compare_annotations.py \
  --summary samples/output/summary.csv \
  --annotations samples/annotation_template.csv \
  --output samples/output/metrics.json
```

Metrics include document type accuracy, patient/date found accuracy, lab result count exact match, average confidence, low-confidence rate, rejection rate, missing lab rows rate, and OCR failure rate.

## Limitations

- This is not a system of record and does not persist results.
- No `/documents/*` or review routes are active in the FastAPI app.
- `file_url` download is not implemented in this MVP.
- Extraction is regex/dictionary based and can miss vendor-specific table layouts.
- OCR accuracy depends on image quality, language packs, and installed OCR engines.
- The backend/dev team must handle auth, storage, database records, review workflow, and patient-profile integration.
