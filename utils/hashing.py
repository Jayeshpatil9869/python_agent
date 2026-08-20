"""Hashing utilities."""

import hashlib


def hash_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
