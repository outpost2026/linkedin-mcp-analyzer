from __future__ import annotations

import re
from typing import Tuple

DEGREE_KEYWORDS = [
    "bachelor",
    "master",
    "phd",
    "degree",
    "university degree",
    "vysokoškolské",
    "titul",
    "bakalář",
    "magisterský",
    "inženýr",
]

FLEXIBILITY_KEYWORDS = [
    "equivalent practical experience",
    "or comparable",
    "or equivalent",
    "or related",
    "ekvivalentní praxe",
    "nebo srovnatelné",
    "welcome but not required",
    "don't meet every requirement",
    "you don't need to tick every box",
]


def formal_score(raw_text: str) -> Tuple[float, str]:
    lowered = raw_text.lower()

    degree_hits = sum(
        1 for kw in DEGREE_KEYWORDS if re.search(re.escape(kw.lower()), lowered)
    )
    flex_hits = sum(
        1 for kw in FLEXIBILITY_KEYWORDS if re.search(re.escape(kw.lower()), lowered)
    )

    if degree_hits > 0 and flex_hits > 0:
        score = 30.0 + min(20.0, float(flex_hits) * 5.0)
        detail = (
            f"Degree required ({degree_hits}x) but flexibility found ({flex_hits}x)"
        )
    elif degree_hits > 0:
        score = 20.0
        detail = f"Degree required ({degree_hits}x), no flexibility clause"
    elif flex_hits > 0:
        score = 55.0
        detail = "No degree requirement mentioned, flexibility encouraged"
    else:
        score = 50.0
        detail = "No formal education signal"

    return round(score, 1), detail
