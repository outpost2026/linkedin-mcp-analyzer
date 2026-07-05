"""Regression tests: EROI engine against known scored entries from KB."""

from linkedin_mcp_custom.analysis.schemas import EROIResult
from linkedin_mcp_custom.analysis.scorer import score_job_from_text


def _check(
    label: str,
    got: EROIResult,
    expected_pct: float,
    tolerance: float = 10.0,
    expected_verdict: str | None = None,
):
    low = expected_pct - tolerance
    high = expected_pct + tolerance
    dims = [(d.name, d.score) for d in got.dimensions]
    assert low <= got.total_score <= high, (
        f"{label}: expected ~{expected_pct}%, got {got.total_score}% "
        f"(range {low}-{high}) dims={dims}"
    )
    if expected_verdict:
        assert got.verdict == expected_verdict, (
            f"{label}: expected verdict {expected_verdict}, got {got.verdict} dims={dims}"
        )
    print(f"  PASS {label}: {got.total_score}% ({got.verdict}) expected {expected_pct}%")


def test_siemens_007():
    text = """
    Test Engineer for Distributed IO Systems. R&D center Prague.
    Industrial automation, Industry 4.0, smart factory, manufacturing.
    Distributed IO modules ET 200. PLC programming, TIA Portal.
    Python, C#, CI/CD pipelines, automated test libraries,
    regression testing, integration testing, Docker.
    AI integration in engineering workflows, Git, Linux.
    Bachelor's/Master's in EE or comparable technical field.
    """
    result = score_job_from_text(
        job_id="007",
        job_title="Test Engineer for Distributed IO Systems",
        company="Siemens",
        raw_text=text,
        location="Praha",
    )
    _check("Siemens #007", result, 82.0, tolerance=10.0, expected_verdict="SLEDOVAT")
    assert "PLC" in [g.skill for g in result.skill_gaps]


def test_desoutter_003():
    text = """
    Light Automation Specialist. Industrial automation and manufacturing.
    PLC programming, robots, cobots, EtherCAT, PROFINET, Modbus TCP, OPC UA.
    Sensors, I/O systems, 2D/3D drawings, wiring diagrams, P&ID.
    ISO/TS 150 safety standards. System integrator with customer-facing role.
    Python scripting for test automation. CI/CD pipelines, Git.
    You don't need to tick every box. Degree in Mechatronics or equivalent practical experience.
    """
    result = score_job_from_text(
        job_id="003",
        job_title="Light Automation Specialist",
        company="Desoutter Tools",
        raw_text=text,
        location="Brno, Jihomoravsky kraj",
    )
    _check("Desoutter #003", result, 72.0, tolerance=12.0)


def test_google_010():
    text = """
    Senior Manufacturing Engineer. Cloud hardware manufacturing.
    SMT assembly, PCBA, final assembly, rack integration of servers.
    Smart factory transformation, AI, predictive maintenance.
    SPC, CP/CPK statistical process control, data analysis.
    AutoCAD, Cadence Allegro, Gerber tools for PCB design.
    Bachelor's in Mechanical/Industrial/Electrical Engineering or equivalent practical experience.
    """
    result = score_job_from_text(
        job_id="010",
        job_title="Senior Manufacturing Engineer",
        company="Google",
        raw_text=text,
        location="Praha",
    )
    _check("Google #010", result, 52.0, tolerance=10.0)


def test_msm_group_015():
    text = """
    Logistics & System Architect / Integrator. Distribution logistics, supply chain.
    API integration, middleware, microservices, event-driven architecture.
    System architecture, technical specification, vendor selection.
    Traceability systems, dashboard design, planning tools.
    Pragmatist who connects systems into functional whole.
    Not primarily a programmer. Master's Degree preferred.
    """
    result = score_job_from_text(
        job_id="015",
        job_title="Logistics & System Architect / Integrator",
        company="MSM GROUP",
        raw_text=text,
        location="Praha",
    )
    _check("MSM GROUP #015", result, 48.0, tolerance=10.0)


def test_apify_001():
    text = """
    Data Engineer. SaaS B2B data platform. Web scraping, AI agents.
    Snowflake, Keboola, dbt, Tableau, n8n, Segment, Census.
    HubSpot, Intercom, Mixpanel, SQL, Python scripting.
    Data engineering experience required, 3+ years.
    English B2, Prague hybrid.
    """
    result = score_job_from_text(
        job_id="001",
        job_title="Data Engineer",
        company="Apify",
        raw_text=text,
        location="Praha",
    )
    _check("Apify #001", result, 38.0, tolerance=10.0)


def test_thermo_fisher_014():
    text = """
    System Integration Engineer. Software deployment for electron microscopes.
    Kubernetes, KVM, virtualization, scripting, deployment automation.
    Networking, configuration management, system-level integration.
    Own system integration across complex HW/SW boundaries.
    Structured troubleshooting methodology.
    Degree in CS/SE or equivalent practical experience.
    """
    result = score_job_from_text(
        job_id="014",
        job_title="System Integration Engineer",
        company="Thermo Fisher Scientific",
        raw_text=text,
        location="Brno",
    )
    _check("Thermo Fisher #014", result, 60.0, tolerance=10.0)


if __name__ == "__main__":
    import sys

    tests = [
        ("Siemens #007", test_siemens_007),
        ("Desoutter #003", test_desoutter_003),
        ("Google #010", test_google_010),
        ("MSM GROUP #015", test_msm_group_015),
        ("Apify #001", test_apify_001),
        ("Thermo Fisher #014", test_thermo_fisher_014),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            print(f"  FAIL {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL {name}: EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 40}")
    if failed:
        print(f"FAILED: {failed}/{len(tests)} tests")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
