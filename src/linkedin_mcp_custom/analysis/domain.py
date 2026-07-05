from __future__ import annotations

import re

from linkedin_mcp_custom.analysis.config import (
    ADJACENT_INDUSTRIAL_KEYWORDS,
    CORE_INDUSTRIAL_KEYWORDS,
    NON_INDUSTRIAL_KEYWORDS,
)

ELECTRONICS_MFG_KEYWORDS = [
    "SMT",
    "PCBA",
    "electronics manufacturing",
    "cloud hardware",
    "rack integration",
    "circuit board",
    "semiconductor",
]


def _count_matches(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    count = 0
    for kw in keywords:
        if re.search(re.escape(kw.lower()), lowered):
            count += 1
    return count


def domain_score(raw_text: str, job_title: str = "") -> tuple[float, str]:
    text = f"{job_title} {raw_text}".lower()
    core_hits = _count_matches(text, CORE_INDUSTRIAL_KEYWORDS)
    adjacent_hits = _count_matches(text, ADJACENT_INDUSTRIAL_KEYWORDS)
    non_industrial_hits = _count_matches(text, NON_INDUSTRIAL_KEYWORDS)
    electronics_hits = _count_matches(text, ELECTRONICS_MFG_KEYWORDS)

    if core_hits >= 5:
        score = 85.0
        detail = f"Strong industrial domain ({core_hits} keywords)"
    elif core_hits >= 3:
        score = 70.0
        detail = f"Core industrial domain ({core_hits} keywords)"
    elif core_hits >= 1:
        score = 45.0 + min(15.0, float(core_hits) * 5.0)
        detail = f"Weak industrial signal ({core_hits} core keywords)"
    elif adjacent_hits >= 3:
        score = 45.0
        detail = f"Adjacent industrial domain ({adjacent_hits} keywords)"
    elif adjacent_hits >= 1:
        score = 30.0 + min(10.0, float(adjacent_hits) * 5.0)
        detail = f"Marginally adjacent ({adjacent_hits} keywords)"
    elif non_industrial_hits >= 3:
        score = 10.0
        detail = f"Non-industrial domain ({non_industrial_hits} noise keywords)"
    elif non_industrial_hits >= 1:
        score = 20.0
        detail = f"Mostly non-industrial ({non_industrial_hits} noise keywords)"
    else:
        score = 25.0
        detail = "No clear domain signal"

    if core_hits == 0 and adjacent_hits == 0 and non_industrial_hits > 0:
        score = min(score, 15.0)
        detail += " (pure noise)"

    if electronics_hits > 0:
        score = min(score, 45.0)
        detail += " (electronics manufacturing, not core industrial)"

    return round(score, 1), detail
