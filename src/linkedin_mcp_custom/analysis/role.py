from __future__ import annotations

import re
from typing import Tuple

from linkedin_mcp_custom.analysis.config import (
    ENGINEERING_ROLE_KEYWORDS,
    FAKE_ENGINEER_KEYWORDS,
)


def role_score(raw_text: str, job_title: str = "") -> Tuple[float, str]:
    text = f"{job_title} {raw_text}".lower()
    title_lower = job_title.lower()

    eng_hits = sum(
        1 for kw in ENGINEERING_ROLE_KEYWORDS if re.search(re.escape(kw.lower()), text)
    )
    fake_hits = sum(
        1 for kw in FAKE_ENGINEER_KEYWORDS if re.search(re.escape(kw.lower()), text)
    )

    is_fake_title = any(
        kw in title_lower
        for kw in ["customer service", "field service", "sales", "support"]
    )
    title_has_engineer = "engineer" in title_lower or "engineering" in title_lower

    if eng_hits > 0 and fake_hits == 0:
        score = 80.0 + min(20.0, float(eng_hits) * 5.0)
        detail = f"Engineering role confirmed ({eng_hits} keywords)"
    elif eng_hits > 0 and fake_hits > 0:
        penalty = min(60.0, float(fake_hits) * 20.0)
        score = max(10.0, 80.0 - penalty)
        detail = f"Engineering keywords ({eng_hits}) with fake-engineer signals ({fake_hits})"
    elif is_fake_title and title_has_engineer:
        score = 15.0
        detail = "Fake engineer pattern detected in title"
    elif title_has_engineer:
        score = 60.0
        detail = "Title contains engineer but weak text signal"
    elif fake_hits > 0:
        score = 20.0
        detail = f"Non-engineering role ({fake_hits} service/sales keywords)"
    else:
        score = 35.0
        detail = "No strong role signal detected"

    return round(score, 1), detail
