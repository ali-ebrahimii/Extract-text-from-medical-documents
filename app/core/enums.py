from enum import Enum

class DocumentType(str, Enum):
    LAB = "lab"
    PAP_SMEAR = "pap_smear"
    RADIOLOGY = "radiology"
    UNKNOWN_MEDICAL = "unknown_medical"
    UNRELATED_DOCUMENT = "unrelated_document"

# TODO: DocumentStatus and VerificationStatus are legacy DB workflow enums kept for
# the db-backed MVP under legacy/. New stateless extraction code should not use
# DocumentStatus to model validation or database workflow.
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    SECURITY_REJECTED = "security_rejected"
    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    INVALID_FILE = "invalid_file"
    UNRELATED_DOCUMENT = "unrelated_document"
    QUALITY_CHECK_FAILED = "quality_check_failed"
    NEEDS_PREPROCESSING = "needs_preprocessing"
    PREPROCESSING = "preprocessing"
    PREPROCESSING_FAILED = "preprocessing_failed"
    POOR_QUALITY = "poor_quality"
    READY_FOR_OCR = "ready_for_ocr"
    OCR_PROCESSING = "ocr_processing"
    OCR_FAILED = "ocr_failed"
    CLASSIFICATION_PROCESSING = "classification_processing"
    EXTRACTION_PROCESSING = "extraction_processing"
    EXTRACTION_FAILED = "extraction_failed"
    PROCESSED = "processed"
    DUPLICATE_DOCUMENT = "duplicate_document"
    # NOTE: the values below describe human-review state and are kept here only
    # for backwards compatibility. New code should use ``VerificationStatus``.
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class VerificationStatus(str, Enum):
    """Human-review state, kept separate from the pipeline ``DocumentStatus``."""

    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
