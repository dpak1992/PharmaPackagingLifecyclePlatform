"""Barcode specification validator.

Validates barcode elements against GS1 dimensional standards
and check digit algorithms.
"""
from __future__ import annotations

from typing import List

from packaging_model.models import ArtworkSpec
from packaging_model.enums import BarcodeType

from validation_engine.models import CheckStatus, Severity, ValidationResult

# GS1 minimum dimensions for EAN-13 at 80% magnification
EAN13_MIN_WIDTH = 29.83  # mm
EAN13_MIN_HEIGHT = 22.85  # mm
EAN13_MIN_MODULE = 0.264  # mm


def _validate_ean13_check_digit(data: str) -> bool:
    """Validate the EAN-13 check digit (last digit)."""
    if len(data) != 13 or not data.isdigit():
        return False
    digits = [int(d) for d in data]
    total = sum(
        d * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(digits[:12])
    )
    expected_check = (10 - (total % 10)) % 10
    return digits[12] == expected_check


def validate_barcodes(artwork: ArtworkSpec) -> List[ValidationResult]:
    """Validate all barcode elements in an artwork specification.

    Checks EAN-13 barcodes for:
    - Correct digit count (13 digits)
    - Valid check digit
    - Minimum dimensions per GS1 standards (80% magnification)
    - Barcode must be assigned to a panel
    """
    results: List[ValidationResult] = []

    for bc in artwork.barcodes:
        if bc.barcode_type == BarcodeType.EAN_13:
            # Check data is exactly 13 digits
            if not bc.data.isdigit() or len(bc.data) != 13:
                results.append(ValidationResult(
                    check_id="BAR-001",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.FAIL,
                    severity=Severity.CRITICAL,
                    message=f"EAN-13 barcode '{bc.id}' data must be exactly "
                            f"13 digits.",
                    details=f"Got: {bc.data!r} ({len(bc.data)} chars)",
                ))
            else:
                # Validate check digit
                if _validate_ean13_check_digit(bc.data):
                    results.append(ValidationResult(
                        check_id="BAR-001",
                        element=f"barcode:{bc.id}",
                        status=CheckStatus.PASS,
                        severity=Severity.CRITICAL,
                        message=f"EAN-13 barcode '{bc.id}' data is valid.",
                    ))
                else:
                    results.append(ValidationResult(
                        check_id="BAR-002",
                        element=f"barcode:{bc.id}",
                        status=CheckStatus.FAIL,
                        severity=Severity.CRITICAL,
                        message=f"EAN-13 barcode '{bc.id}' has invalid "
                                f"check digit.",
                        details=f"Data: {bc.data!r}",
                    ))

            # Check dimensions — width
            if bc.width >= EAN13_MIN_WIDTH:
                results.append(ValidationResult(
                    check_id="BAR-003",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.PASS,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' width meets GS1 minimum.",
                ))
            else:
                results.append(ValidationResult(
                    check_id="BAR-003",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.FAIL,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' width is below GS1 minimum.",
                    details=f"Width: {bc.width}mm, minimum: {EAN13_MIN_WIDTH}mm",
                ))

            # Check dimensions — height
            if bc.height >= EAN13_MIN_HEIGHT:
                results.append(ValidationResult(
                    check_id="BAR-004",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.PASS,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' height meets GS1 minimum.",
                ))
            else:
                results.append(ValidationResult(
                    check_id="BAR-004",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.FAIL,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' height is below GS1 minimum.",
                    details=f"Height: {bc.height}mm, minimum: {EAN13_MIN_HEIGHT}mm",
                ))

            # Module width check (approximate: EAN-13 has 95 modules)
            module_width = bc.width / 95.0
            if module_width >= EAN13_MIN_MODULE:
                results.append(ValidationResult(
                    check_id="BAR-005",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.PASS,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' module width meets minimum.",
                ))
            else:
                results.append(ValidationResult(
                    check_id="BAR-005",
                    element=f"barcode:{bc.id}",
                    status=CheckStatus.FAIL,
                    severity=Severity.MAJOR,
                    message=f"Barcode '{bc.id}' module width is below minimum.",
                    details=f"Module width: {module_width:.3f}mm, "
                            f"minimum: {EAN13_MIN_MODULE}mm",
                ))

        # Panel assignment check (applies to all barcode types)
        if bc.panel_type is not None:
            results.append(ValidationResult(
                check_id="BAR-006",
                element=f"barcode:{bc.id}",
                status=CheckStatus.PASS,
                severity=Severity.MAJOR,
                message=f"Barcode '{bc.id}' is assigned to panel "
                        f"'{bc.panel_type.value}'.",
            ))
        else:
            results.append(ValidationResult(
                check_id="BAR-006",
                element=f"barcode:{bc.id}",
                status=CheckStatus.FAIL,
                severity=Severity.MAJOR,
                message=f"Barcode '{bc.id}' is not assigned to any panel.",
            ))

    return results
