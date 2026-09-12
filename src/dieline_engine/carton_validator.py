"""Carton validation against common cartoning machine constraints.

Validates a CartonSpec against typical pharmaceutical cartoner limits,
blister fit, and structural feasibility rules.
"""
from __future__ import annotations

from typing import List

from packaging_model.models import CartonSpec, BlisterSpec
from validation_engine.models import ValidationResult, CheckStatus, Severity


def validate_carton(carton: CartonSpec, blister: BlisterSpec) -> List[ValidationResult]:
    """Validate a CartonSpec against cartoning machine constraints and blister fit.

    Checks dimensional feasibility, blister clearance, board specification,
    and common machine limitations.

    Args:
        carton: The carton specification to validate.
        blister: The blister specification the carton must hold.

    Returns:
        A list of ValidationResult entries (pass, fail, or warning).
    """
    results: List[ValidationResult] = []

    # --- Internal dimensions must be positive ---
    if carton.internal_length <= 0 or carton.internal_width <= 0 or carton.internal_depth <= 0:
        results.append(ValidationResult(
            check_id="CARTON-DIM-POS",
            element="carton",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            message="Internal dimensions must all be positive.",
            details=(
                f"L={carton.internal_length}, W={carton.internal_width}, "
                f"D={carton.internal_depth}"
            ),
        ))
        # If dimensions are not positive, many other checks are meaningless
        return results

    # --- Blister fit: length ---
    min_length = blister.length + 2 * carton.clearance
    if carton.internal_length < min_length:
        results.append(ValidationResult(
            check_id="CARTON-FIT-L",
            element="carton.internal_length",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            message=(
                f"Internal length {carton.internal_length:.1f} mm is too short "
                f"for blister ({blister.length:.1f} mm + 2 x {carton.clearance:.1f} mm clearance = "
                f"{min_length:.1f} mm required)."
            ),
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-FIT-L",
            element="carton.internal_length",
            status=CheckStatus.PASS,
            severity=Severity.CRITICAL,
            message="Internal length accommodates blister with clearance.",
        ))

    # --- Blister fit: width ---
    min_width = blister.width + 2 * carton.clearance
    if carton.internal_width < min_width:
        results.append(ValidationResult(
            check_id="CARTON-FIT-W",
            element="carton.internal_width",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            message=(
                f"Internal width {carton.internal_width:.1f} mm is too narrow "
                f"for blister ({blister.width:.1f} mm + 2 x {carton.clearance:.1f} mm clearance = "
                f"{min_width:.1f} mm required)."
            ),
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-FIT-W",
            element="carton.internal_width",
            status=CheckStatus.PASS,
            severity=Severity.CRITICAL,
            message="Internal width accommodates blister with clearance.",
        ))

    # --- Blister fit: depth ---
    min_depth = blister.height + carton.clearance
    if carton.internal_depth < min_depth:
        results.append(ValidationResult(
            check_id="CARTON-FIT-D",
            element="carton.internal_depth",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            message=(
                f"Internal depth {carton.internal_depth:.1f} mm is too shallow "
                f"for blister ({blister.height:.1f} mm + {carton.clearance:.1f} mm clearance = "
                f"{min_depth:.1f} mm required)."
            ),
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-FIT-D",
            element="carton.internal_depth",
            status=CheckStatus.PASS,
            severity=Severity.CRITICAL,
            message="Internal depth accommodates blister with clearance.",
        ))

    # --- Minimum carton dimensions (typical cartoner minimums) ---
    min_limits = {"L": (carton.internal_length, 40.0), "W": (carton.internal_width, 20.0), "D": (carton.internal_depth, 12.0)}
    for axis, (val, minimum) in min_limits.items():
        if val < minimum:
            results.append(ValidationResult(
                check_id=f"CARTON-MIN-{axis}",
                element=f"carton.internal_{'length' if axis == 'L' else 'width' if axis == 'W' else 'depth'}",
                status=CheckStatus.FAIL,
                severity=Severity.MAJOR,
                message=(
                    f"Internal {axis} dimension {val:.1f} mm is below typical "
                    f"cartoner minimum of {minimum:.1f} mm."
                ),
            ))
        else:
            results.append(ValidationResult(
                check_id=f"CARTON-MIN-{axis}",
                element=f"carton.internal_{'length' if axis == 'L' else 'width' if axis == 'W' else 'depth'}",
                status=CheckStatus.PASS,
                severity=Severity.MAJOR,
                message=f"Internal {axis} dimension meets minimum cartoner requirement.",
            ))

    # --- Maximum carton dimensions ---
    max_limits = {"L": (carton.internal_length, 250.0), "W": (carton.internal_width, 150.0), "D": (carton.internal_depth, 100.0)}
    for axis, (val, maximum) in max_limits.items():
        if val > maximum:
            results.append(ValidationResult(
                check_id=f"CARTON-MAX-{axis}",
                element=f"carton.internal_{'length' if axis == 'L' else 'width' if axis == 'W' else 'depth'}",
                status=CheckStatus.FAIL,
                severity=Severity.MAJOR,
                message=(
                    f"Internal {axis} dimension {val:.1f} mm exceeds typical "
                    f"cartoner maximum of {maximum:.1f} mm."
                ),
            ))
        else:
            results.append(ValidationResult(
                check_id=f"CARTON-MAX-{axis}",
                element=f"carton.internal_{'length' if axis == 'L' else 'width' if axis == 'W' else 'depth'}",
                status=CheckStatus.PASS,
                severity=Severity.MAJOR,
                message=f"Internal {axis} dimension within maximum cartoner limit.",
            ))

    # --- Glue tab width ---
    glue_tab_width = 15.0  # standard, matches geometry.py
    if glue_tab_width < 12.0:
        results.append(ValidationResult(
            check_id="CARTON-GLUE-W",
            element="dieline.glue_tab_width",
            status=CheckStatus.FAIL,
            severity=Severity.MAJOR,
            message=f"Glue tab width {glue_tab_width:.1f} mm is below minimum 12.0 mm.",
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-GLUE-W",
            element="dieline.glue_tab_width",
            status=CheckStatus.PASS,
            severity=Severity.MAJOR,
            message=f"Glue tab width {glue_tab_width:.1f} mm meets minimum requirement.",
        ))

    # --- Board caliper range ---
    cal = carton.board.caliper
    if cal < 0.28:
        results.append(ValidationResult(
            check_id="CARTON-CALIPER",
            element="carton.board.caliper",
            status=CheckStatus.FAIL,
            severity=Severity.MAJOR,
            message=f"Board caliper {cal:.2f} mm is below standard folding boxboard minimum (0.28 mm).",
        ))
    elif cal > 0.60:
        results.append(ValidationResult(
            check_id="CARTON-CALIPER",
            element="carton.board.caliper",
            status=CheckStatus.FAIL,
            severity=Severity.MAJOR,
            message=f"Board caliper {cal:.2f} mm exceeds standard folding boxboard maximum (0.60 mm).",
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-CALIPER",
            element="carton.board.caliper",
            status=CheckStatus.PASS,
            severity=Severity.MAJOR,
            message=f"Board caliper {cal:.2f} mm is within standard range (0.28-0.60 mm).",
        ))

    # --- Tuck flap depth (50-90% of internal width) ---
    tuck_depth = carton.internal_width * 0.80  # matches geometry.py
    tuck_min = carton.internal_width * 0.50
    tuck_max = carton.internal_width * 0.90
    if tuck_depth < tuck_min or tuck_depth > tuck_max:
        results.append(ValidationResult(
            check_id="CARTON-TUCK-DEPTH",
            element="dieline.tuck_flap_depth",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=(
                f"Tuck flap depth {tuck_depth:.1f} mm is outside the typical "
                f"range (50-90% of width = {tuck_min:.1f}-{tuck_max:.1f} mm)."
            ),
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-TUCK-DEPTH",
            element="dieline.tuck_flap_depth",
            status=CheckStatus.PASS,
            severity=Severity.MINOR,
            message=f"Tuck flap depth {tuck_depth:.1f} mm is within typical range.",
        ))

    # --- Clearance range (1.0-4.0mm per side) ---
    if carton.clearance < 1.0:
        results.append(ValidationResult(
            check_id="CARTON-CLEARANCE",
            element="carton.clearance",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=f"Clearance {carton.clearance:.1f} mm is below recommended minimum (1.0 mm).",
        ))
    elif carton.clearance > 4.0:
        results.append(ValidationResult(
            check_id="CARTON-CLEARANCE",
            element="carton.clearance",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=f"Clearance {carton.clearance:.1f} mm exceeds recommended maximum (4.0 mm).",
        ))
    else:
        results.append(ValidationResult(
            check_id="CARTON-CLEARANCE",
            element="carton.clearance",
            status=CheckStatus.PASS,
            severity=Severity.MINOR,
            message=f"Clearance {carton.clearance:.1f} mm is within recommended range.",
        ))

    # --- Warn if depth < 15mm (difficult for cartoning machine) ---
    if carton.internal_depth < 15.0:
        results.append(ValidationResult(
            check_id="CARTON-DEPTH-WARN",
            element="carton.internal_depth",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=(
                f"Internal depth {carton.internal_depth:.1f} mm is below 15 mm. "
                f"This may cause difficulties with cartoning machine handling."
            ),
        ))

    # --- Warn if aspect ratio L/W > 5 ---
    if carton.internal_width > 0:
        ratio = carton.internal_length / carton.internal_width
        if ratio > 5.0:
            results.append(ValidationResult(
                check_id="CARTON-ASPECT",
                element="carton",
                status=CheckStatus.WARNING,
                severity=Severity.MINOR,
                message=(
                    f"Aspect ratio L/W = {ratio:.1f} exceeds 5.0. "
                    f"This is unusual and may cause feeding issues."
                ),
            ))

    return results
