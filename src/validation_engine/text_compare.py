"""Text comparison engine for artwork validation.

Compares artwork text content against an approved source text string
using sequence matching to detect missing or extra content.
"""
from __future__ import annotations

import difflib
from typing import List

from packaging_model.models import ArtworkSpec

from validation_engine.models import CheckStatus, Severity, ValidationResult


def compare_text(
    artwork: ArtworkSpec, approved_text: str
) -> List[ValidationResult]:
    """Compare artwork text content against an approved source text.

    Extracts all text content from the artwork's text elements, compares
    it against the approved source text using difflib.SequenceMatcher,
    and returns structured results flagging missing or extra content.
    """
    results: List[ValidationResult] = []

    # Extract all text from artwork elements
    artwork_text = " ".join(el.content for el in artwork.text_elements)

    # Compute similarity ratio
    matcher = difflib.SequenceMatcher(None, approved_text, artwork_text)
    ratio = matcher.ratio()

    # Overall match ratio result
    if ratio >= 0.95:
        status = CheckStatus.PASS
    elif ratio >= 0.80:
        status = CheckStatus.WARNING
    else:
        status = CheckStatus.FAIL

    results.append(ValidationResult(
        check_id="TEXT-001",
        element="overall_match",
        status=status,
        severity=Severity.MAJOR,
        message=f"Text match ratio: {ratio:.2%}",
        details=f"Artwork text length: {len(artwork_text)}, "
                f"Approved text length: {len(approved_text)}",
    ))

    # Tokenize into words for phrase-level comparison
    approved_words = approved_text.split()
    artwork_words = artwork_text.split()

    word_matcher = difflib.SequenceMatcher(None, approved_words, artwork_words)

    missing_phrases: List[str] = []
    extra_phrases: List[str] = []

    for tag, i1, i2, j1, j2 in word_matcher.get_opcodes():
        if tag == "delete":
            # In approved but not in artwork — missing
            phrase = " ".join(approved_words[i1:i2])
            missing_phrases.append(phrase)
        elif tag == "insert":
            # In artwork but not in approved — extra
            phrase = " ".join(artwork_words[j1:j2])
            extra_phrases.append(phrase)
        elif tag == "replace":
            # Content differs
            missing_phrases.append(" ".join(approved_words[i1:i2]))
            extra_phrases.append(" ".join(artwork_words[j1:j2]))

    # Report missing phrases
    if missing_phrases:
        results.append(ValidationResult(
            check_id="TEXT-002",
            element="missing_text",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            message=f"Found {len(missing_phrases)} missing phrase(s) "
                    f"from approved text.",
            details="; ".join(missing_phrases),
        ))
    else:
        results.append(ValidationResult(
            check_id="TEXT-002",
            element="missing_text",
            status=CheckStatus.PASS,
            severity=Severity.CRITICAL,
            message="No missing phrases detected.",
        ))

    # Report extra content
    if extra_phrases:
        results.append(ValidationResult(
            check_id="TEXT-003",
            element="extra_text",
            status=CheckStatus.WARNING,
            severity=Severity.MAJOR,
            message=f"Found {len(extra_phrases)} extra phrase(s) "
                    f"not in approved text.",
            details="; ".join(extra_phrases),
        ))
    else:
        results.append(ValidationResult(
            check_id="TEXT-003",
            element="extra_text",
            status=CheckStatus.PASS,
            severity=Severity.MAJOR,
            message="No extra phrases detected.",
        ))

    return results
