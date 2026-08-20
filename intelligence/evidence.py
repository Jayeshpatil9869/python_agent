"""Evidence tracking."""

from typing import Any

from pydantic import BaseModel, Field

from intelligence.confidence import ConfidenceLevel


class EvidenceItem(BaseModel):
    source: str
    description: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED


class EvidenceCollection(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)

    def add(
        self,
        source: str,
        description: str,
        data: dict[str, Any] | None = None,
        confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED,
    ) -> None:
        self.items.append(
            EvidenceItem(
                source=source,
                description=description,
                data=data or {},
                confidence=confidence,
            )
        )
