#!/usr/bin/env python
"""Compare pipeline summary.csv against manual annotations and emit simple metrics.

Example:
    python scripts/compare_annotations.py \
        --summary samples/output/summary.csv \
        --annotations samples/annotation_template.csv \
        --output samples/output/metrics.json

Metrics are computed only over rows where the corresponding annotation field is
present (blank annotations are skipped, never guessed).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


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


def compute_metrics(summary: list[dict], annotations: list[dict]) -> dict:
    ann_by_file = {a.get("filename"): a for a in annotations}
    dtype_pairs: list[tuple] = []
    name_pairs: list[tuple[bool, bool]] = []
    date_pairs: list[tuple[bool, bool]] = []
    lab_exact: list[bool] = []
    extraction_confs: list[float] = []
    needs_review = 0
    rejected = 0
    n = 0

    for row in summary:
        n += 1
        if str(row.get("verification_status")).strip() == "needs_review":
            needs_review += 1
        if str(row.get("verification_status")).strip() == "rejected" or str(row.get("validation_status")).strip() in {"unrelated_document", "poor_quality", "ocr_failed", "invalid_file", "unsupported_file_type", "duplicate_document"}:
            rejected += 1
        try:
            extraction_confs.append(float(row.get("extraction_confidence")))
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
        "average_extraction_confidence": round(sum(extraction_confs) / len(extraction_confs), 4) if extraction_confs else None,
        "needs_review_rate": round(needs_review / n, 4) if n else None,
        "rejection_rate": round(rejected / n, 4) if n else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    summary = _read_csv(Path(args.summary))
    annotations = _read_csv(Path(args.annotations))
    metrics = compute_metrics(summary, annotations)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
