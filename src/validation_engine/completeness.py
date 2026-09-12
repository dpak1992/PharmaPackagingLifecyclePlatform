"""Regulatory completeness checker for Indian pharmaceutical packaging.

Verifies that all mandatory labeling elements required by the D&C Act
Rules 96/96A are present in the artwork specification.
"""
from __future__ import annotations

from typing import List

from packaging_model.models import PackagingConfig, ArtworkSpec

from validation_engine.models import CheckStatus, Severity, ValidationResult


def _all_text_content(artwork: ArtworkSpec) -> str:
    """Concatenate all text element content into a single searchable string."""
    return " ".join(el.content for el in artwork.text_elements)


def _all_coding_purposes(artwork: ArtworkSpec) -> str:
    """Concatenate all coding zone purposes into a single searchable string."""
    return " ".join(cz.purpose for cz in artwork.coding_zones)


def _check_text_contains(
    artwork: ArtworkSpec,
    search_text: str,
    check_id: str,
    element_name: str,
    severity: Severity,
    case_sensitive: bool = False,
) -> ValidationResult:
    """Check if any text element contains the given search text."""
    all_text = _all_text_content(artwork)
    haystack = all_text if case_sensitive else all_text.upper()
    needle = search_text if case_sensitive else search_text.upper()

    if needle in haystack:
        return ValidationResult(
            check_id=check_id,
            element=element_name,
            status=CheckStatus.PASS,
            severity=severity,
            message=f"{element_name} found in artwork text.",
        )
    return ValidationResult(
        check_id=check_id,
        element=element_name,
        status=CheckStatus.FAIL,
        severity=severity,
        message=f"{element_name} is missing from artwork text.",
        details=f"Expected text containing: {search_text!r}",
    )


def _check_coding_zone(
    artwork: ArtworkSpec,
    search_text: str,
    check_id: str,
    element_name: str,
    severity: Severity,
) -> ValidationResult:
    """Check if any coding zone purpose contains the given search text."""
    purposes = _all_coding_purposes(artwork)
    if search_text.upper() in purposes.upper():
        return ValidationResult(
            check_id=check_id,
            element=element_name,
            status=CheckStatus.PASS,
            severity=severity,
            message=f"{element_name} coding zone found.",
        )
    return ValidationResult(
        check_id=check_id,
        element=element_name,
        status=CheckStatus.FAIL,
        severity=severity,
        message=f"{element_name} coding zone is missing.",
        details=f"Expected a coding zone with purpose containing: {search_text!r}",
    )


def check_completeness(
    config: PackagingConfig, artwork: ArtworkSpec
) -> List[ValidationResult]:
    """Check artwork for all mandatory Indian pharma labeling elements.

    Validates against D&C Act Rules 96/96A requirements.

    Returns a list of ValidationResult objects, one per mandatory element.
    """
    product = config.product
    results: List[ValidationResult] = []

    # 1. Brand name
    results.append(_check_text_contains(
        artwork, product.brand_name,
        "COMP-001", "Brand name", Severity.CRITICAL,
    ))

    # 2. Generic name
    results.append(_check_text_contains(
        artwork, product.generic_name,
        "COMP-002", "Generic name", Severity.CRITICAL,
    ))

    # 3. Strength
    results.append(_check_text_contains(
        artwork, str(product.strength),
        "COMP-003", "Strength", Severity.CRITICAL,
    ))

    # 4. Composition
    results.append(_check_text_contains(
        artwork, product.composition,
        "COMP-004", "Composition", Severity.CRITICAL,
    ))

    # 5. Pack size
    results.append(_check_text_contains(
        artwork, config.pack_size,
        "COMP-005", "Pack size", Severity.MAJOR,
    ))

    # 6. Batch number area
    results.append(_check_coding_zone(
        artwork, "B.No",
        "COMP-006", "Batch number", Severity.CRITICAL,
    ))

    # 7. Manufacturing date area
    results.append(_check_coding_zone(
        artwork, "Mfg",
        "COMP-007", "Manufacturing date", Severity.CRITICAL,
    ))

    # 8. Expiry date area
    results.append(_check_coding_zone(
        artwork, "Exp",
        "COMP-008", "Expiry date", Severity.CRITICAL,
    ))

    # 9. MRP (only if config.mrp is set)
    if config.mrp:
        results.append(_check_coding_zone(
            artwork, "MRP",
            "COMP-009", "MRP", Severity.MAJOR,
        ))

    # 10. Manufacturer name
    results.append(_check_text_contains(
        artwork, product.manufacturer.name,
        "COMP-010", "Manufacturer name", Severity.CRITICAL,
    ))

    # 11. Manufacturing license number
    results.append(_check_text_contains(
        artwork, product.manufacturer.license_no,
        "COMP-011", "Manufacturing license", Severity.CRITICAL,
    ))

    # 12. Schedule H warning
    results.append(_check_text_contains(
        artwork, "SCHEDULE H",
        "COMP-012", "Schedule H warning", Severity.CRITICAL,
    ))

    # 13. Storage conditions
    results.append(_check_text_contains(
        artwork, product.storage_conditions,
        "COMP-013", "Storage conditions", Severity.MAJOR,
    ))

    # 14. Keep out of reach of children (or "Keep medicine out of reach of children")
    results.append(_check_text_contains(
        artwork, "out of reach of children",
        "COMP-014", "Children warning", Severity.MAJOR,
    ))

    return results
