"""Confidence classification system."""

from enum import Enum


class ConfidenceLevel(str, Enum):
    DETECTED = "DETECTED"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"
