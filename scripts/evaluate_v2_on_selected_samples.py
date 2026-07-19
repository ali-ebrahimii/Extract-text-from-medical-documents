#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.extraction_pipeline_v2 import ExtractionInputV2, ExtractionPipelineV2


METRIC_LABELS = {
    "total_files_processed": "total files processed",
    "recommended_save_count": "recommended_save count",
    "manual_review_count": "manual_review count",
    "reupload_recommended_count": "reupload_recommended count",
    "clean_pdfs_recommended_save_count": "clean PDFs recommended save count",
    "image_recommended_save_count": "image recommended save count",
    "backend_safe_row_count": "backend-safe row count",
    "image_rows_with_backend_row_save_recommendation_true": "image rows with backend_row_save_recommendation=true",
    "unsafe_doctor_name_in_safe_payload_count": "unsafe doctor_name in safe payload count",
    "false_bacteria_48_or_culture_48_count": "false Bacteria=48/Culture=48 count",
    "normal_ast_alt_falsely_low_count": "normal AST/ALT falsely Low count",
    "national_id_schema_violations_count": "national_id schema violations count",
    "tracking_number_missing_in_clean_pdfs_count": "tracking_number missing in clean PDFs count",
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def is_clean_pdf(path: Path, data) -> bool:
    return path.suffix.lower() == ".pdf" and data.document.page_context.template_type == "tav_text_pdf"


def new_metrics() -> dict[str, int]:
    return {key: 0 for key in METRIC_LABELS}


def national_id_schema_violated(national_id: dict) -> bool:
    if not national_id:
        return False
    if "value" in national_id:
        return True
    return not {"raw_value", "masked_value", "hash_sha256"}.intersection(national_id)


def evaluate(samples_dir: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = new_metrics()

    if not samples_dir.exists():
        print("samples_dir_missing")
        return metrics

    pipeline = ExtractionPipelineV2()
    for sample_path in sorted(path for path in samples_dir.rglob("*") if path.is_file()):
        media_type = mimetypes.guess_type(sample_path.name)[0] or "application/octet-stream"
        result = pipeline.process(
            ExtractionInputV2(
                str(sample_path),
                sample_path.name,
                media_type,
                privacy_mode="internal",
            )
        )
        data = result.model_dump(mode="json", exclude_none=True)
        (output_dir / f"{sample_path.name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

        recommendation = result.persistence_recommendation
        image = is_image(sample_path)
        clean_pdf = is_clean_pdf(sample_path, result)

        metrics["total_files_processed"] += 1
        metrics["recommended_save_count"] += int(recommendation.recommended_save)
        metrics["manual_review_count"] += int(recommendation.recommended_action == "manual_review")
        metrics["reupload_recommended_count"] += int(recommendation.recommended_action == "reupload_recommended")
        metrics["clean_pdfs_recommended_save_count"] += int(clean_pdf and recommendation.recommended_save)
        metrics["image_recommended_save_count"] += int(image and recommendation.recommended_save)

        metrics["backend_safe_row_count"] += sum(int(row.backend_row_save_recommendation) for row in result.lab_results)
        image_backend_recommended_rows = sum(
            int(row.backend_row_save_recommendation) for row in result.lab_results
        )
        if image:
            metrics["image_rows_with_backend_row_save_recommendation_true"] += image_backend_recommended_rows

        metrics["unsafe_doctor_name_in_safe_payload_count"] += int(
            "doctor_name" in result.safe_payload_candidate.get("common_fields", {})
        )

        for row in result.lab_results:
            metrics["false_bacteria_48_or_culture_48_count"] += int(
                row.test_name_standard in ("Bacteria", "Urine Culture", "Culture")
                and row.result_numeric == 48
            )
            metrics["normal_ast_alt_falsely_low_count"] += int(
                row.test_name_standard in ("AST", "ALT")
                and row.unit in ("U/L", "IU/L")
                and row.flag == "Low"
            )

        national_id = result.common_fields.get("national_id", {})
        metrics["national_id_schema_violations_count"] += int(
            national_id_schema_violated(national_id)
        )
        metrics["tracking_number_missing_in_clean_pdfs_count"] += int(
            clean_pdf
            and not result.common_fields.get("tracking_number", {}).get("field_backend_usable")
        )

    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-dir", required=True)
    parser.add_argument("--reference-dir", help="Accepted for compatibility only; reference-output validation is not implemented.")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics = evaluate(Path(args.samples_dir), Path(args.output_dir))
    for key, label in METRIC_LABELS.items():
        print(f"{label}: {metrics[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
