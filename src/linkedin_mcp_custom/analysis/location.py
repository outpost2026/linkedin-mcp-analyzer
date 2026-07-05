from __future__ import annotations

import re

from linkedin_mcp_custom.analysis.config import (
    CZECH_KEYWORDS,
    OFFICE_KEYWORDS,
    REMOTE_KEYWORDS,
)

DISTANT_CZ_KEYWORDS = [
    "Cheb",
    "Světlá nad Sázavou",
    "Karlovy Vary",
    "Karviná",
    "Frýdek-Místek",
    "Šumperk",
    "Jeseník",
]


def location_score(location: str, raw_text: str = "") -> tuple[float, str]:
    text = f"{location} {raw_text}".lower()

    remote_hits = sum(1 for kw in REMOTE_KEYWORDS if re.search(re.escape(kw.lower()), text))
    czech_hits = sum(1 for kw in CZECH_KEYWORDS if re.search(re.escape(kw.lower()), text))
    office_hits = sum(1 for kw in OFFICE_KEYWORDS if re.search(re.escape(kw.lower()), text))
    distant_hits = sum(1 for kw in DISTANT_CZ_KEYWORDS if re.search(re.escape(kw.lower()), text))

    if distant_hits > 0:
        score = max(5.0, 30.0 - float(distant_hits) * 15.0)
        detail = f"Distant location detected ({distant_hits}x)"
        return round(score, 1), detail

    if remote_hits >= 2:
        score = 95.0
        detail = "Strong remote/hybrid signal"
    elif remote_hits >= 1:
        score = 80.0
        detail = "Remote or hybrid work available"
    elif czech_hits >= 1:
        base = 70.0
        if office_hits > 0:
            base -= min(20.0, float(office_hits) * 10.0)
        score = base
        detail = f"CZ-based role ({czech_hits} location keywords)"
    elif office_hits > 0:
        score = 35.0
        detail = "Office-only role"
    else:
        score = 50.0
        detail = "No clear location/mode signal"

    return round(score, 1), detail
