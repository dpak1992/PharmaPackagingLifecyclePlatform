"""Shared data models for the validation engine."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class ValidationResult(BaseModel):
    check_id: str
    element: str
    status: CheckStatus
    severity: Severity
    message: str
    details: Optional[str] = None
