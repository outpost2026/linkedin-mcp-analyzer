from __future__ import annotations

import re

from linkedin_mcp_custom.analysis.config import SKILL_MATRIX
from linkedin_mcp_custom.analysis.schemas import TechMatch


def tech_score(raw_text: str) -> tuple[float, list[TechMatch], str]:
    lowered = raw_text.lower()
    matched_skills: list[TechMatch] = []
    mentioned_weighted = 0.0
    matched_weighted = 0.0

    for skill, config in SKILL_MATRIX.items():
        pattern = re.escape(skill.lower())
        if re.search(pattern, lowered):
            weight = float(config["weight"])
            match_type = str(config["match"])
            matched_skills.append(TechMatch(skill=skill, match=match_type, weight=weight))
            mentioned_weighted += weight
            if match_type in ("direct_match", "partial_match"):
                matched_weighted += weight

    if mentioned_weighted == 0:
        return 0.0, matched_skills, "No skills detected in posting"

    max_possible = sum(float(item["weight"]) for item in SKILL_MATRIX.values())
    if max_possible == 0:
        return 0.0, matched_skills, "No skills defined"

    match_ratio = matched_weighted / mentioned_weighted
    coverage = mentioned_weighted / max_possible
    coverage_multiplier = min(1.0, coverage * 5.0)
    score = match_ratio * coverage_multiplier * 100.0

    if not matched_skills:
        detail = "No skill matches found"
    else:
        direct = sum(1 for s in matched_skills if s.match == "direct_match")
        partial = sum(1 for s in matched_skills if s.match == "partial_match")
        detail = f"{direct} direct, {partial} partial matches"

    return round(min(score, 100.0), 1), matched_skills, detail
