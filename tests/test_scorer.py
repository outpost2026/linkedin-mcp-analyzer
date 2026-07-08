"""Unit tests for individual EROI scorer dimensions."""

from linkedin_mcp_custom.analysis.domain import domain_score
from linkedin_mcp_custom.analysis.formal import formal_score
from linkedin_mcp_custom.analysis.growth import growth_score
from linkedin_mcp_custom.analysis.location import location_score
from linkedin_mcp_custom.analysis.role import role_score
from linkedin_mcp_custom.analysis.tech import tech_score


# ── domain_score tests ───────────────────────────────────────────────


def test_domain_strong_core():
    score, detail = domain_score(
        "industrial automation smart factory manufacturing PLC SCADA robotics "
        "CNC CAM production assembly control system process control "
        "sensor actuator system integration"
    )
    assert score >= 80.0, f"Expected strong domain >= 80, got {score}"
    assert "Strong" in detail


def test_domain_core_threshold_3():
    score, detail = domain_score("industrial automation manufacturing PLC")
    assert 60.0 <= score <= 80.0, f"Expected 60-80 for 3 core, got {score}"
    assert "Core" in detail


def test_domain_adjacent_only():
    score, detail = domain_score(
        "IoT embedded systems automotive supply chain hardware prototyping"
    )
    assert 30.0 <= score <= 55.0, f"Expected 30-55 for adjacent, got {score}"


def test_domain_non_industrial():
    score, detail = domain_score(
        "customer service sales help desk frontend web developer UI/UX digital marketing insurance"
    )
    assert score <= 20.0, f"Expected <= 20 for non-industrial, got {score}"


def test_domain_electronics_mfg_cap():
    score, detail = domain_score(
        "SMT PCBA electronics manufacturing cloud hardware rack integration "
        "circuit board semiconductor industrial automation manufacturing"
    )
    assert score <= 45.0, f"Expected <= 45 for electronics mfg, got {score}"


def test_domain_pure_noise():
    score, detail = domain_score("insurance financial services banking human resources recruiting")
    assert score <= 25.0, f"Expected <= 25 for pure noise, got {score}"


# ── tech_score tests ─────────────────────────────────────────────────


def test_tech_full_match():
    score, matches, detail = tech_score("Python reverse engineering CI/CD Git Docker Linux")
    assert score >= 30.0, f"Expected >= 30 for good skill match, got {score}"
    assert len(matches) >= 5


def test_tech_no_match():
    score, matches, detail = tech_score(
        "This is a completely unrelated text with no technical skills whatsoever"
    )
    assert score == 0.0, f"Expected 0 for no match, got {score}"
    assert len(matches) == 0


def test_tech_empty_text():
    score, matches, detail = tech_score("")
    assert score == 0.0


# ── role_score tests ─────────────────────────────────────────────────


def test_role_engineer_confirmed():
    score, detail = role_score(
        "system integration engineering R&D development test automation",
        "Senior System Integration Engineer",
    )
    assert score >= 80.0, f"Expected >= 80 for engineering role, got {score}"


def test_role_fake_engineer():
    score, detail = role_score("customer service field service sales support", "Sales Engineer")
    assert score == 60.0, f"Expected 60 for fake engineer (penalized), got {score}"
    assert "fake" in detail.lower()


def test_role_engineer_title_strong_signal():
    score, detail = role_score("completely unrelated non-technical text", "Software Engineer")
    assert score >= 85.0, f"Expected >= 85 from title + kw match, got {score}"


def test_role_service_only():
    score, detail = role_score(
        "customer service support help desk ticketing", "Customer Service Representative"
    )
    assert score <= 30.0, f"Expected <= 30 for service role, got {score}"


def test_role_no_signal():
    score, detail = role_score("some random content with no keywords whatsoever")
    assert 30.0 <= score <= 45.0, f"Expected ~35 for no signal, got {score}"


# ── growth_score tests ────────────────────────────────────────────────


def test_growth_strategic_employer():
    score, detail = growth_score("Siemens")
    assert score == 100.0, f"Expected 100 for Siemens, got {score}"


def test_growth_growth_employer():
    score, detail = growth_score("Atlas Copco")
    assert score == 60.0, f"Expected 60 for Atlas Copco, got {score}"


def test_growth_non_strategic():
    score, detail = growth_score("Some Unknown Company s.r.o.")
    assert score == 20.0, f"Expected 20 for unknown, got {score}"


def test_growth_empty():
    score, detail = growth_score("")
    assert score == 20.0


# ── formal_score tests ───────────────────────────────────────────────


def test_formal_degree_with_flexibility():
    score, detail = formal_score(
        "Bachelor's degree required or equivalent practical experience. "
        "You don't need to tick every box."
    )
    assert 30.0 <= score <= 55.0, f"Expected 30-55 for degree+flex, got {score}"


def test_formal_degree_only():
    score, detail = formal_score(
        "Master's degree in Electrical Engineering required. Bachelor's in Computer Science."
    )
    assert score == 20.0, f"Expected 20 for degree-only, got {score}"


def test_formal_flexibility_only():
    score, detail = formal_score("Equivalent practical experience welcome but not required")
    assert 50.0 <= score <= 60.0, f"Expected ~55 for flex-only, got {score}"


def test_formal_no_signal():
    score, detail = formal_score(
        "We are looking for a motivated team player to join our growing organization."
    )
    assert score == 50.0, f"Expected 50 for no signal, got {score}"


# ── location_score tests ──────────────────────────────────────────────


def test_location_strong_remote():
    score, detail = location_score("Remote", "Fully remote position work from home anywhere")
    assert score >= 80.0, f"Expected >= 80 for strong remote, got {score}"


def test_location_hybrid():
    score, detail = location_score(
        "Praha, Czech Republic", "This role is hybrid work with home office option"
    )
    assert score >= 80.0, f"Expected >= 80 for hybrid+remote signal, got {score}"


def test_location_cz_office():
    score, detail = location_score("Praha", "Office-based position in Prague")
    assert 50.0 <= score <= 75.0, f"Expected ~50-75 for CZ office, got {score}"


def test_location_cz_based():
    score, detail = location_score("Brno, Jihomoravsky kraj", "Work from our Brno office")
    assert 50.0 <= score <= 75.0, f"Expected ~50-75 for CZ role, got {score}"


def test_location_distant():
    score, detail = location_score("Cheb, Czech Republic", "")
    assert score <= 40.0, f"Expected <= 40 for distant, got {score}"


def test_location_office_only():
    score, detail = location_score("Praha", "On-site office position only")
    assert 30.0 <= score <= 50.0, f"Expected ~35 for office-only, got {score}"
