"""Structured analyzer stage results."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    NO_DATA = "no_data"


class Finding(BaseModel):
    value: Any = None
    status: str = "UNKNOWN"
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    source: str = ""
    notes: str | None = None


class AnalyzerResult(BaseModel):
    stage: str
    status: StageStatus = StageStatus.SUCCESS
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    def mark_failed(self, reason: str) -> None:
        self.status = StageStatus.FAILED
        self.errors.append(reason)

    def mark_partial(self, reason: str) -> None:
        if self.status == StageStatus.SUCCESS:
            self.status = StageStatus.PARTIAL
        self.warnings.append(reason)

    def mark_no_data(self, reason: str) -> None:
        self.status = StageStatus.NO_DATA
        self.warnings.append(reason)
