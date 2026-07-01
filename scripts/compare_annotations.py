#!/usr/bin/env python
"""Compare stateless extraction summary.csv against manual annotations."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REJECTION_STATUSES = {
    "unsupported_file",
    "invalid_file",
    "poor_quality",
    "ocr_failed",
    "unrelated_document",
    "extraction_failed",
}


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _present(value: str | None) -> bool:
    return value is not None and str(value).strip() != ""


def _accuracy(pairs: list[tuple[bool, bool]]) -> float | None:
    if not pairs:
        return None
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 4)


def _codes(value: str | None) -> set[str]:
    return {part.strip() for part in str(value or "").split("|") if part.strip()}


def compute_metrics(summary: list[dict], annotations: list[dict]) -> dict:
    ann_by_file = {a.get("filename"): a for a in annotations}
    dtype_pairs: list[tuple[str, str]] = []
    name_pairs: list[tuple[bool, bool]] = []
    date_pairs: list[tuple[bool, bool]] = []
    lab_exact: list[bool] = []
    confidences: list[float] = []
    low_confidence = 0
    rejected = 0
    missing_lab_rows = 0
    ocr_failed = 0
    n = 0

    for row in summary:
        n += 1
        status = str(row.get("status") or "").strip()
        warning_codes = _codes(row.get("warning_codes"))
        if status == "low_confidence":
            low_confidence += 1
        if status in REJECTION_STATUSES:
            rejected += 1
        if "MISSING_LAB_ROWS" in warning_codes:
            missing_lab_rows += 1
        if status == "ocr_failed":
            ocr_failed += 1
        try:
            confidences.append(float(row.get("confidence")))
        except (TypeError, ValueError):
            pass

        ann = ann_by_file.get(row.get("filename"))
        if not ann:
            continue
        if _present(ann.get("expected_document_type")):
            dtype_pairs.append((str(row.get("document_type")).strip(), ann["expected_document_type"].strip()))
        if _present(ann.get("expected_patient_name")):
            name_pairs.append((_truthy(row.get("patient_name_found")), True))
        if _present(ann.get("expected_date")):
            date_pairs.append((_truthy(row.get("date_found")), True))
        if _present(ann.get("expected_lab_result_count")):
            try:
                lab_exact.append(int(row.get("lab_result_count") or 0) == int(ann["expected_lab_result_count"]))
            except ValueError:
                pass

    return {
        "documents_evaluated": n,
        "annotated_documents": sum(1 for r in summary if r.get("filename") in ann_by_file),
        "document_type_accuracy": round(sum(1 for a, b in dtype_pairs if a == b) / len(dtype_pairs), 4) if dtype_pairs else None,
        "patient_name_found_accuracy": _accuracy(name_pairs),
        "date_found_accuracy": _accuracy(date_pairs),
        "lab_result_count_exact_match": round(sum(lab_exact) / len(lab_exact), 4) if lab_exact else None,
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "low_confidence_rate": round(low_confidence / n, 4) if n else None,
        "rejection_rate": round(rejected / n, 4) if n else None,
        "missing_lab_rows_rate": round(missing_lab_rows / n, 4) if n else None,
        "ocr_failure_rate": round(ocr_failed / n, 4) if n else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    metrics = compute_metrics(_read_csv(Path(args.summary)), _read_csv(Path(args.annotations)))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
