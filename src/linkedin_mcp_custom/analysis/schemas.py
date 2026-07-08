"""Data schemas for EROI scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class SkillConfig(TypedDict):
    weight: float
    match: str


@dataclass
class TechMatch:
    """Skill match result for a single technology."""

    skill: str
    match: str  # direct_match | partial_match | no_match
    weight: float = 1.0


@dataclass
class DimensionScore:
    """Score for one EROI dimension."""

    name: str
    weight: float
    score: float
    detail: str = ""


@dataclass
class EROIResult:
    """Complete EROI analysis result for one job."""

    job_id: str
    job_title: str
    company: str

    total_score: float
    verdict: str  # SLEDOVAT | MEDIUM | HRANICNI | NESLEDOVAT

    dimensions: list[DimensionScore] = field(default_factory=list)
    skill_gaps: list[TechMatch] = field(default_factory=list)
    mismatch_dimensions: list[str] = field(default_factory=list)
    recommendation: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON/metadata output."""
        return {
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "total_score": self.total_score,
            "verdict": self.verdict,
            "dimensions": [
                {
                    "name": d.name,
                    "weight": d.weight,
                    "score": d.score,
                    "weighted": round(d.score * d.weight / 100, 1),
                    "detail": d.detail,
                }
                for d in self.dimensions
            ],
            "skill_gaps": [
                {
                    "skill": g.skill,
                    "match": g.match,
                }
                for g in self.skill_gaps
            ],
            "mismatch_dimensions": self.mismatch_dimensions,
            "recommendation": self.recommendation,
        }


@dataclass
class JobFeatures:
    """Extracted features from raw job text — input to EROI engine."""

    raw_text: str
    job_title: str = ""
    company: str = ""
    location: str = ""
    seniority: str = ""
    employment_type: str = ""
    applicants_count: int = 0
    job_id: str = ""

    # Benefits (optional — parsed from text)
    has_bonus: bool = False
    has_equity: bool = False
    has_car_benefit: bool = False
    salary_range: str = ""
