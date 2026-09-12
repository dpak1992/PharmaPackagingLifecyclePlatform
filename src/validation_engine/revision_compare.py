"""Artwork revision comparator.

Compares two ArtworkSpec versions to detect changes between revisions,
including added, removed, and modified elements.
"""
from __future__ import annotations

from typing import List

from packaging_model.models import ArtworkSpec

from validation_engine.models import CheckStatus, Severity, ValidationResult


def compare_revisions(
    old: ArtworkSpec, new: ArtworkSpec
) -> List[ValidationResult]:
    """Compare two artwork revisions and report all changes.

    Detects added, removed, and modified text elements, barcodes,
    coding zones, and spot colors.
    """
    results: List[ValidationResult] = []

    # --- Text elements ---
    old_text_ids = {el.id for el in old.text_elements}
    new_text_ids = {el.id for el in new.text_elements}
    old_text_map = {el.id: el for el in old.text_elements}
    new_text_map = {el.id: el for el in new.text_elements}

    for tid in sorted(new_text_ids - old_text_ids):
        results.append(ValidationResult(
            check_id="REV-001",
            element=f"text:{tid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Text element '{tid}' was added.",
            details=f"Content: {new_text_map[tid].content!r}",
        ))

    for tid in sorted(old_text_ids - new_text_ids):
        results.append(ValidationResult(
            check_id="REV-002",
            element=f"text:{tid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Text element '{tid}' was removed.",
            details=f"Previous content: {old_text_map[tid].content!r}",
        ))

    for tid in sorted(old_text_ids & new_text_ids):
        old_el = old_text_map[tid]
        new_el = new_text_map[tid]
        if old_el.content != new_el.content:
            results.append(ValidationResult(
                check_id="REV-003",
                element=f"text:{tid}",
                status=CheckStatus.WARNING,
                severity=Severity.MAJOR,
                message=f"Text element '{tid}' content was modified.",
                details=f"Old: {old_el.content!r} -> New: {new_el.content!r}",
            ))

    # --- Barcodes ---
    old_bc_ids = {bc.id for bc in old.barcodes}
    new_bc_ids = {bc.id for bc in new.barcodes}
    old_bc_map = {bc.id: bc for bc in old.barcodes}
    new_bc_map = {bc.id: bc for bc in new.barcodes}

    for bid in sorted(new_bc_ids - old_bc_ids):
        results.append(ValidationResult(
            check_id="REV-004",
            element=f"barcode:{bid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Barcode '{bid}' was added.",
        ))

    for bid in sorted(old_bc_ids - new_bc_ids):
        results.append(ValidationResult(
            check_id="REV-005",
            element=f"barcode:{bid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Barcode '{bid}' was removed.",
        ))

    for bid in sorted(old_bc_ids & new_bc_ids):
        old_bc = old_bc_map[bid]
        new_bc = new_bc_map[bid]
        if old_bc.data != new_bc.data or old_bc.barcode_type != new_bc.barcode_type:
            results.append(ValidationResult(
                check_id="REV-006",
                element=f"barcode:{bid}",
                status=CheckStatus.WARNING,
                severity=Severity.CRITICAL,
                message=f"Barcode '{bid}' was modified.",
                details=f"Old data: {old_bc.data!r} -> New data: {new_bc.data!r}",
            ))

    # --- Coding zones ---
    old_cz_ids = {cz.id for cz in old.coding_zones}
    new_cz_ids = {cz.id for cz in new.coding_zones}
    old_cz_map = {cz.id: cz for cz in old.coding_zones}
    new_cz_map = {cz.id: cz for cz in new.coding_zones}

    for cid in sorted(new_cz_ids - old_cz_ids):
        results.append(ValidationResult(
            check_id="REV-007",
            element=f"coding_zone:{cid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Coding zone '{cid}' was added.",
        ))

    for cid in sorted(old_cz_ids - new_cz_ids):
        results.append(ValidationResult(
            check_id="REV-008",
            element=f"coding_zone:{cid}",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Coding zone '{cid}' was removed.",
        ))

    for cid in sorted(old_cz_ids & new_cz_ids):
        old_cz = old_cz_map[cid]
        new_cz = new_cz_map[cid]
        if old_cz.purpose != new_cz.purpose:
            results.append(ValidationResult(
                check_id="REV-009",
                element=f"coding_zone:{cid}",
                status=CheckStatus.WARNING,
                severity=Severity.MAJOR,
                message=f"Coding zone '{cid}' purpose was modified.",
                details=f"Old: {old_cz.purpose!r} -> New: {new_cz.purpose!r}",
            ))

    # --- Spot colors ---
    old_colors = {c.name for c in old.spot_colors}
    new_colors = {c.name for c in new.spot_colors}

    for cname in sorted(new_colors - old_colors):
        results.append(ValidationResult(
            check_id="REV-010",
            element=f"color:{cname}",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=f"Spot color '{cname}' was added.",
        ))

    for cname in sorted(old_colors - new_colors):
        results.append(ValidationResult(
            check_id="REV-011",
            element=f"color:{cname}",
            status=CheckStatus.WARNING,
            severity=Severity.MINOR,
            message=f"Spot color '{cname}' was removed.",
        ))

    # If no changes detected
    if not results:
        results.append(ValidationResult(
            check_id="REV-000",
            element="artwork",
            status=CheckStatus.PASS,
            severity=Severity.MINOR,
            message="No changes detected between revisions.",
        ))

    return results
