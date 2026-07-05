from __future__ import annotations

from linkedin_mcp_custom.analysis.config import DIMENSION_WEIGHTS, THRESHOLDS
from linkedin_mcp_custom.analysis.schemas import DimensionScore, EROIResult, JobFeatures
from linkedin_mcp_custom.analysis.domain import domain_score
from linkedin_mcp_custom.analysis.tech import tech_score
from linkedin_mcp_custom.analysis.role import role_score
from linkedin_mcp_custom.analysis.growth import growth_score
from linkedin_mcp_custom.analysis.formal import formal_score
from linkedin_mcp_custom.analysis.location import location_score


def _determine_verdict(total: float) -> str:
    for threshold, label in THRESHOLDS:
        if total >= threshold:
            return label
    return "NESLEDOVAT"


def _recommendation(total_score: float) -> str:
    if total_score >= 65.0:
        return "Aplikovat — silný lead"
    if total_score >= 50.0:
        return "Zvážit aplikaci — střední fit, nutná mitigace gapů"
    if total_score >= 40.0:
        return "Hraniční — aplikovat jen pokud zbývající čas"
    return "Nealokovat čas"


def score_job(features: JobFeatures) -> EROIResult:
    d_score, d_detail = domain_score(features.raw_text, features.job_title)
    t_score, skill_gaps, t_detail = tech_score(features.raw_text)
    r_score, r_detail = role_score(features.raw_text, features.job_title)
    g_score, g_detail = growth_score(features.company)
    f_score, f_detail = formal_score(features.raw_text)
    l_score, l_detail = location_score(features.location, features.raw_text)

    dimensions = [
        DimensionScore(
            name="domain",
            weight=DIMENSION_WEIGHTS["domain"],
            score=d_score,
            detail=d_detail,
        ),
        DimensionScore(
            name="tech",
            weight=DIMENSION_WEIGHTS["tech"],
            score=t_score,
            detail=t_detail,
        ),
        DimensionScore(
            name="role",
            weight=DIMENSION_WEIGHTS["role"],
            score=r_score,
            detail=r_detail,
        ),
        DimensionScore(
            name="growth",
            weight=DIMENSION_WEIGHTS["growth"],
            score=g_score,
            detail=g_detail,
        ),
        DimensionScore(
            name="formal",
            weight=DIMENSION_WEIGHTS["formal"],
            score=f_score,
            detail=f_detail,
        ),
        DimensionScore(
            name="location",
            weight=DIMENSION_WEIGHTS["location"],
            score=l_score,
            detail=l_detail,
        ),
    ]

    total_score = sum(d.score * d.weight for d in dimensions)
    verdict = _determine_verdict(total_score)

    mismatch_dimensions = [d.name for d in dimensions if d.score < 35.0]

    notes_parts = []
    if "domain" in mismatch_dimensions:
        notes_parts.append("Domain mismatch kritický")
    if "tech" in mismatch_dimensions:
        notes_parts.append(f"Tech gap: {len(skill_gaps)} skill mismatches")
    if "role" in mismatch_dimensions:
        notes_parts.append("Role mismatch (fake engineer or non-engineering)")
    if d_score >= 40 and r_score >= 80:
        notes_parts.append("Positioning match zachraňuje domain gap")

    return EROIResult(
        job_id=features.job_id or "unknown",
        job_title=features.job_title or "Unknown",
        company=features.company or "Unknown",
        total_score=round(total_score, 1),
        verdict=verdict,
        dimensions=dimensions,
        skill_gaps=skill_gaps,
        mismatch_dimensions=mismatch_dimensions,
        recommendation=_recommendation(total_score),
        notes="; ".join(notes_parts),
    )


def score_job_from_text(
    job_id: str,
    job_title: str,
    company: str,
    raw_text: str,
    location: str = "",
) -> EROIResult:
    features = JobFeatures(
        raw_text=raw_text,
        job_title=job_title,
        company=company,
        location=location,
        job_id=job_id,
    )
    return score_job(features)
