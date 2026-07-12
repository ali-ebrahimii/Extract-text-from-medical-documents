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

Use JSON with exactly one of `file_path`, `base64_content`, or `file_url`. For backend integration, prefer `file_url`: the backend should send a short-lived pre-signed HTTP(S) URL for the document/image. The service downloads the content into a temporary file, processes it, deletes the temporary file, and returns only `ExtractionResponse` JSON. No downloaded files are permanently saved.

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


URL example for backend integration:

```json
{
  "request_id": "req-123",
  "document_id": "doc-456",
  "file_url": "https://storage.example.com/temp/report.pdf?signature=...",
  "file_name": "report.pdf",
  "mime_type": "application/pdf",
  "debug": false
}
```

URL security behavior:

- Only `http://` and `https://` schemes are parsed; by default, public `https://` URLs are required when no allow-list is configured.
- Unsupported schemes such as `file://`, `ftp://`, and `s3://` are rejected.
- Downloads use connection/read timeouts, streaming chunks, a redirect limit, and the `MAX_UPLOAD_MB` size limit.
- Empty downloads and non-200 HTTP responses are rejected.
- Localhost, loopback, private, link-local, reserved, and metadata-service IPs are blocked unless private hosts are explicitly enabled for a controlled environment.
- `file_name` is derived from the request, `Content-Disposition`, URL path basename, or `downloaded_file`; when the derived name has no supported extension, the service appends one from supported PDF/image MIME types. `mime_type` is derived from the request, `Content-Type`, or file extension. `.jpg`/`.jpeg` inputs normalize to `image/jpeg`.

URL configuration:

```env
FILE_URL_ALLOWED_HOSTS=
FILE_URL_ALLOW_PRIVATE_HOSTS=false
FILE_URL_TIMEOUT_SECONDS=15
FILE_URL_MAX_REDIRECTS=3
```

If `FILE_URL_ALLOWED_HOSTS` is empty, only public HTTPS URLs are allowed. If set, only those hostnames/domains are allowed (comma-separated; wildcard subdomains like `*.example.com` are supported). Private/internal IPs remain blocked unless `FILE_URL_ALLOW_PRIVATE_HOSTS=true`.

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
- `INVALID_REQUEST`
- `INVALID_FILE_URL`
- `URL_SCHEME_NOT_ALLOWED`
- `URL_HOST_NOT_ALLOWED`
- `URL_PRIVATE_HOST_BLOCKED`
- `URL_DOWNLOAD_TIMEOUT`
- `URL_DOWNLOAD_FAILED`
- `URL_FILE_TOO_LARGE`
- `URL_EMPTY_FILE`
- `URL_CONTENT_TYPE_UNSUPPORTED`
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
- `file_url` download supports HTTP(S) pre-signed temporary URLs. Authorization-header based URL downloads are not supported yet.
- Extraction is regex/dictionary based and can miss vendor-specific table layouts.
- OCR accuracy depends on image quality, language packs, and installed OCR engines.
- The backend/dev team must handle auth, storage, database records, review workflow, and patient-profile integration.

## Backend user-files integration

The stateless extraction service can orchestrate extraction for files that are owned by a separate backend. The backend remains responsible for permanent storage, database records, authentication, saved results, and any review UI. This service only lists, temporarily fetches, extracts, returns results, and deletes temporary files.

### Endpoint

`POST /extract/user-files`

Request:

```json
{
  "request_id": "req-123",
  "user_id": "user-456",
  "debug": false,
  "max_files": 10
}
```

Example response:

```json
{
  "request_id": "req-123",
  "user_id": "user-456",
  "status": "partial_success",
  "total_files": 3,
  "processed_files": 2,
  "failed_files": 1,
  "results": [
    {
      "file_name": "lab1.pdf",
      "document_id": "doc-1",
      "status": "success",
      "result": {},
      "errors": [],
      "warnings": []
    }
  ],
  "errors": [],
  "warnings": []
}
```

### Backend configuration

```env
BACKEND_FILE_LIST_URL_TEMPLATE=https://backend.example.com/api/users/{user_id}/files
BACKEND_FILE_FETCH_URL_TEMPLATE=https://backend.example.com/api/users/{user_id}/files/{file_name}
BACKEND_API_TOKEN=
BACKEND_API_TIMEOUT_SECONDS=15
BACKEND_API_MAX_FILES=50
BACKEND_API_FILE_RESPONSE_MODE=auto
```

`BACKEND_FILE_LIST_URL_TEMPLATE` should return either an array of file names:

```json
["lab1.pdf", "image1.jpg"]
```

or an array of file descriptors:

```json
[
  {
    "file_name": "lab1.pdf",
    "document_id": "doc-1",
    "mime_type": "application/pdf",
    "size_bytes": 12345
  }
]
```

`BACKEND_FILE_FETCH_URL_TEMPLATE` can return binary file content, JSON with a temporary/pre-signed `file_url`, or JSON with `base64_content`. Set `BACKEND_API_FILE_RESPONSE_MODE` to `auto`, `binary`, `json_url`, or `json_base64`. In `auto` mode, JSON responses are inspected for `file_url` or `base64_content`; all other responses are treated as binary files.

Backend implementations should preferably return either binary content or a pre-signed temporary `file_url`. The extraction service does not persist fetched files or extraction results, does not create permanent storage directories, and processes all backend files through temporary files only.
