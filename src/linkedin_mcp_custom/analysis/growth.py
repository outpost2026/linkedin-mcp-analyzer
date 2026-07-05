from __future__ import annotations

from linkedin_mcp_custom.analysis.config import GROWTH_EMPLOYERS, STRATEGIC_EMPLOYERS


def growth_score(company: str) -> tuple[float, str]:
    if not company:
        return 20.0, "Unknown employer"

    company_lower = company.lower()

    for emp in STRATEGIC_EMPLOYERS:
        if emp.lower() in company_lower:
            return 100.0, f"Strategic employer: {emp}"

    for emp in GROWTH_EMPLOYERS:
        if emp.lower() in company_lower:
            return 60.0, f"Growth employer: {emp}"

    return 20.0, "Non-strategic employer"
