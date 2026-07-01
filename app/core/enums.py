from enum import Enum


class DocumentType(str, Enum):
    LAB = "lab"
    PAP_SMEAR = "pap_smear"
    RADIOLOGY = "radiology"
    UNKNOWN_MEDICAL = "unknown_medical"
    UNRELATED_DOCUMENT = "unrelated_document"
