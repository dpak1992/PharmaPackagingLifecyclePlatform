"""Artwork validation engine for pharmaceutical packaging.

Provides deterministic, rule-based validation of artwork specifications
against Indian pharmaceutical regulatory requirements (D&C Act Rules 96/96A).
"""
from validation_engine.models import Severity, CheckStatus, ValidationResult
from validation_engine.completeness import check_completeness
from validation_engine.text_compare import compare_text
from validation_engine.revision_compare import compare_revisions
from validation_engine.barcode_validate import validate_barcodes

__all__ = [
    "Severity",
    "CheckStatus",
    "ValidationResult",
    "check_completeness",
    "compare_text",
    "compare_revisions",
    "validate_barcodes",
]
