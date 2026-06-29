#!/usr/bin/env python
"""Offline evaluation harness for the medical-document extraction pipeline.

Processes a folder of real PDFs/images through the *same* pipeline the API uses
(no FastAPI server required) and exports per-document JSON, OCR text, and a CSV
summary. Intended for measuring real extraction quality on real samples.

Example:
    python scripts/evaluate_samples.py \
        --input-dir samples/raw \
        --output-dir samples/output \
        --reset-db --limit 20
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./eval_medical_documents.db")

# Make the project importable when run directly (python scripts/evaluate_samples.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import init_db  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.document import Base, MedicalDocument  # noqa: E402
from app.services.storage_service import StorageService  # noqa: E402
from app.services.pipeline_service import PipelineService  # noqa: E402
from app.api.routes.documents import rich_doc  # noqa: E402

MIME_MAP = {".pdf":"application/pdf",".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}
SUPPORTED = set(MIME_MAP)

CSV_COLUMNS = [
    "filename", "document_id", "validation_status", "verification_status",
    "document_type", "document_type_confidence", "relevance_score",
    "quality_score_before", "quality_score_after", "ocr_confidence",
    "ocr_text_length", "extraction_confidence", "patient_name_found",
    "national_id_hash_found", "date_found", "test_or_report_name_found",
    "lab_result_count", "pap_smear_found", "radiology_found",
    "patient_name_value_masked_or_present", "center_name_found", "tracking_number_found",
    "age_found", "sex_found", "false_positive_suspected_count", "ocr_warning_count",
    "quality_worst_page_number", "quality_min_score",
    "rejection_reason", "warnings",
]


def _found(field) -> bool:
    return bool(field and field.get("value"))


def _summary_row(filename: str, response: dict) -> dict:
    common = response.get("common_fields") or {}
    extracted = response.get("extracted_data") or {}
    nid = common.get("national_id") or {}
    quality_details = ((response.get("quality") or {}).get("details") or {})
    warnings = response.get("warnings") or []
    lab_results = extracted.get("lab_results") or []
    fp_count = sum(1 for r in lab_results if (r.get("test_name_standard") or "").lower() in {"high","desirable","average risk","low risk","borderline hight"})
    return {
        "filename": filename,
        "document_id": response.get("document_id"),
        "validation_status": response.get("validation_status"),
        "verification_status": response.get("verification_status"),
        "document_type": response.get("document_type"),
        "document_type_confidence": response.get("document_type_confidence"),
        "relevance_score": response.get("relevance_score"),
        "quality_score_before": response.get("quality_score_before"),
        "quality_score_after": response.get("quality_score_after"),
        "ocr_confidence": (response.get("ocr") or {}).get("confidence"),
        "ocr_text_length": (response.get("ocr") or {}).get("text_length"),
        "extraction_confidence": response.get("extraction_confidence"),
        "patient_name_found": _found(common.get("patient_name")),
        "national_id_hash_found": bool(nid.get("hash")),
        "date_found": _found(common.get("date_of_test_or_report")),
        "test_or_report_name_found": _found(common.get("test_or_report_name")),
        "patient_name_value_masked_or_present": _found(common.get("patient_name")),
        "center_name_found": _found(common.get("center_name")),
        "tracking_number_found": _found(common.get("tracking_number")),
        "age_found": _found(common.get("age")),
        "sex_found": _found(common.get("sex")),
        "false_positive_suspected_count": fp_count,
        "ocr_warning_count": len([w for w in warnings if "ocr" in str(w).lower()]),
        "quality_worst_page_number": quality_details.get("worst_page_number"),
        "quality_min_score": quality_details.get("min_quality_score"),
        "lab_result_count": len(lab_results),
        "pap_smear_found": bool(extracted.get("pap_smear_reports")),
        "radiology_found": bool(extracted.get("radiology_reports")),
        "rejection_reason": response.get("rejection_reason"),
        "warnings": "|".join(warnings),
    }


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def process_file(db, path: Path, copy_files: bool) -> dict:
    stored_path, size, digest = StorageService().save_file(str(path), copy=copy_files)
    ext = path.suffix.lower()
    content_type = MIME_MAP.get(ext, "application/octet-stream")
    doc = MedicalDocument(
        original_file_path=stored_path, original_file_name=path.name,
        original_file_type=content_type, file_size_bytes=size, file_hash=digest,
        validation_status="uploaded", verification_status="unverified",
    )
    db.add(doc); db.commit(); db.refresh(doc)
    doc = PipelineService().process_document(db, doc.id)
    return rich_doc(doc, db)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--reset-db", action="store_true", help="drop+recreate tables and clear output dir")
    ap.add_argument("--limit", type=int, default=0, help="process at most N files (0 = all)")
    ap.add_argument("--yes", action="store_true", help="confirm destructive non-SQLite --reset-db")
    ap.add_argument("--copy-files", default="true", choices=["true", "false"],
                    help="copy inputs into storage/originals (default true)")
    args = ap.parse_args(argv)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.is_dir():
        print(f"Input dir not found: {input_dir}", file=sys.stderr)
        return 2

    db_url=os.environ.get("DATABASE_URL", "sqlite:///./eval_medical_documents.db")
    if args.reset_db:
        print(f"Reset requested for database: {db_url}")
        if not db_url.startswith("sqlite") and not args.yes:
            print("Refusing to reset a non-SQLite database without --yes", file=sys.stderr); return 2
    if args.reset_db and output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "json").mkdir(parents=True, exist_ok=True)
    (output_dir / "ocr").mkdir(parents=True, exist_ok=True)

    init_db()
    if args.reset_db:
        reset_database()

    files = sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"No supported files in {input_dir} ({', '.join(sorted(SUPPORTED))})", file=sys.stderr)
        return 1

    summary_path = output_dir / "summary.csv"
    copy_files = args.copy_files == "true"
    rows: list[dict] = []
    db = SessionLocal()
    try:
        for i, path in enumerate(files, 1):
            stem = path.stem
            try:
                response = process_file(db, path, copy_files)
            except Exception as exc:  # never let one bad file abort the batch
                print(f"[{i}/{len(files)}] ERROR {path.name}: {exc}", file=sys.stderr)
                rows.append({**{c: None for c in CSV_COLUMNS}, "filename": path.name,
                             "rejection_reason": f"pipeline_error: {exc}"})
                continue
            (output_dir / "json" / f"{stem}.json").write_text(
                json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
            (output_dir / "ocr" / f"{stem}.txt").write_text(
                _ocr_text(db, response), encoding="utf-8")
            rows.append(_summary_row(path.name, response))
            print(f"[{i}/{len(files)}] {path.name} -> {response.get('validation_status')} "
                  f"/ {response.get('verification_status')}")
    finally:
        db.close()

    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {summary_path}")
    return 0


def _ocr_text(db, response: dict) -> str:
    # rich_doc does not embed full OCR text; fetch it from the document row.
    doc = db.get(MedicalDocument, response.get("document_id"))
    return (doc.ocr_text if doc else "") or ""


if __name__ == "__main__":
    raise SystemExit(main())
