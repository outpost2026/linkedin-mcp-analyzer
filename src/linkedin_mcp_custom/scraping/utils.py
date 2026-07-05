"""Scraping utilities — noise stripping, selectors, constants."""

from __future__ import annotations

import re

# Common noise patterns to strip from extracted text
NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(r"LinkedIn\s+(and\s+)?\d{4}", re.IGNORECASE),
    re.compile(r"About\s+us\s*$", re.IGNORECASE),
    re.compile(r"Privacy\s+Policy\s*$", re.IGNORECASE),
    re.compile(r"Terms\s+of\s+Service\s*$", re.IGNORECASE),
    re.compile(r"Cookie\s+Policy\s*$", re.IGNORECASE),
    re.compile(r"Send\s+feedback\s*$", re.IGNORECASE),
    re.compile(r"Help\s+Center\s*$", re.IGNORECASE),
    re.compile(r"Accessibility\s*$", re.IGNORECASE),
    re.compile(r"Ad\s+Choices\s*$", re.IGNORECASE),
    re.compile(r"Get\s+the\s+LinkedIn\s+app\s*$", re.IGNORECASE),
    re.compile(r"More\s+tab\s+to\s+explore", re.IGNORECASE),
]

# Rate-limit signal sentinel
RATE_LIMITED_MSG = "[[RATE_LIMITED]]"

# LinkedIn URLs
LINKEDIN_BASE = "https://www.linkedin.com"
JOBS_TRACKER_URL = f"{LINKEDIN_BASE}/jobs-tracker/"
JOB_VIEW_URL = f"{LINKEDIN_BASE}/jobs/view/"


def strip_noise(text: str) -> str:
    """Remove common LinkedIn noise from extracted text."""
    lines = text.split("\n")
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip lines matching noise patterns
        if any(p.search(stripped) for p in NOISE_PATTERNS):
            continue

        cleaned.append(stripped)

    return "\n".join(cleaned)


def is_rate_limited(text: str) -> bool:
    """Check if the page shows a rate-limit message."""
    signals = [
        "too many requests",
        "rate limited",
        "please try again later",
        "unusual traffic",
    ]
    lower = text.lower()
    return any(s in lower for s in signals)
