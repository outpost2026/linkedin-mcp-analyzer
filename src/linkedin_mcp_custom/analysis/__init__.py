"""Shared utilities for EROI analysis."""

from __future__ import annotations

import re
import unicodedata


def strip_diacritics(s: str) -> str:
    """Remove Czech/European diacritics for robust text matching.

    Example: 'TECHNICKÝ PRACOVNÍK' -> 'TECHNICKY PRACOVNIK'
    """
    nfkd = unicodedata.normalize("NFKD", s)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def normalize(s: str) -> str:
    """Full normalization: lowercase, strip whitespace, remove diacritics."""
    return re.sub(r"\s+", " ", strip_diacritics(s).strip().lower())


def normalize_keywords(keywords: list[str]) -> list[str]:
    """Normalize a keyword list for case-insensitive, diacritics-free matching."""
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        nk = normalize(kw)
        if nk not in seen:
            seen.add(nk)
            result.append(nk)
    return result
