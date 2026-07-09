"""Tests for SyntheticReportGenerator — statistics, clustering, output format."""

import json
import tempfile
from pathlib import Path

from linkedin_mcp_custom.analysis.report_generator import SyntheticReportGenerator


def _sample_entries() -> list[dict]:
    return [
        {
            "id": "001",
            "title": "System Integration Engineer",
            "company": {"industry": "Thermo Fisher Scientific"},
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": ["CAM", "IoT", "scripting"],
                    "partial_match": ["AI"],
                    "no_match": ["Kubernetes"],
                }
            },
            "eroi": {
                "fit_score_pct": 76.5,
                "verdict": "SLEDOVAT",
                "mismatch_dimensions": ["location"],
            },
        },
        {
            "id": "002",
            "title": "Automotive CI/CD Engineer (DevOps)",
            "company": {"industry": "Digiteq Automotive"},
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": ["Python", "CI/CD", "Git", "Linux"],
                    "partial_match": ["AI"],
                    "no_match": ["C++", "Kubernetes", "Azure"],
                }
            },
            "eroi": {
                "fit_score_pct": 60.2,
                "verdict": "MEDIUM",
                "mismatch_dimensions": ["growth"],
            },
        },
        {
            "id": "003",
            "title": "AI / ML / LLM Research Engineer",
            "company": {"industry": "Sourcein"},
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": [],
                    "partial_match": ["LLM", "AI"],
                    "no_match": [],
                }
            },
            "eroi": {
                "fit_score_pct": 38.5,
                "verdict": "NESLEDOVAT",
                "mismatch_dimensions": ["domain", "tech", "growth"],
            },
        },
        {
            "id": "004",
            "title": "PLC Software Engineer",
            "company": {"industry": "Sécheron SA"},
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": [],
                    "partial_match": ["AI"],
                    "no_match": ["PLC"],
                }
            },
            "eroi": {
                "fit_score_pct": 58.9,
                "verdict": "MEDIUM",
                "mismatch_dimensions": ["tech", "growth", "formal"],
            },
        },
        {
            "id": "005",
            "title": "Automation Systems Engineer IoT",
            "company": {"industry": "Resideo"},
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": ["IoT", "ESP32", "Python"],
                    "partial_match": ["AI"],
                    "no_match": ["AWS", "C#"],
                }
            },
            "eroi": {
                "fit_score_pct": 60.9,
                "verdict": "MEDIUM",
                "mismatch_dimensions": ["growth", "formal"],
            },
        },
    ]


def test_verdict_distribution():
    entries = _sample_entries()
    dist = SyntheticReportGenerator._compute_verdict_dist(entries)
    assert dist.get("SLEDOVAT") == 1
    assert dist.get("MEDIUM") == 3
    assert dist.get("NESLEDOVAT") == 1
    print(f"  PASS verdict_dist: {dist}")


def test_scores():
    entries = _sample_entries()
    scores = SyntheticReportGenerator._compute_scores(entries)
    assert len(scores) == 5
    assert max(scores) == 76.5
    assert min(scores) == 38.5
    print(f"  PASS scores: {scores}")


def test_skill_frequency():
    entries = _sample_entries()
    freq = SyntheticReportGenerator._compute_skill_frequency(entries)
    assert freq.get("AI") == 5
    assert freq.get("IoT") == 2
    assert freq.get("C++") == 1
    assert freq.get("Python") == 2
    print(f"  PASS skill_freq: {dict(list(freq.items())[:5])}...")


def test_snr():
    entries = _sample_entries()
    snr = SyntheticReportGenerator._compute_snr(entries)
    assert snr["CAM"]["snr_pct"] == 100.0
    assert snr["AI"]["snr_pct"] == 20.0
    print(f"  PASS SNR: CAM=100%, AI=20%")


def test_mismatch_frequency():
    entries = _sample_entries()
    mf = SyntheticReportGenerator._compute_mismatch_freq(entries)
    assert mf.get("growth") == 4
    assert mf.get("formal") == 2
    assert mf.get("tech") == 2
    print(f"  PASS mismatch: {mf}")


def test_cluster_detection_industrial():
    entry = _sample_entries()[0]
    cluster = SyntheticReportGenerator._detect_cluster(entry)
    assert cluster == "industrial_automation_core"
    print(f"  PASS cluster (industrial): {cluster}")


def test_cluster_detection_ai():
    entry = _sample_entries()[2]
    cluster = SyntheticReportGenerator._detect_cluster(entry)
    assert cluster == "ai_ml_hype"
    print(f"  PASS cluster (AI/ML): {cluster}")


def test_cluster_detection_enterprise():
    entry = _sample_entries()[1]
    cluster = SyntheticReportGenerator._detect_cluster(entry)
    assert cluster == "enterprise_it"
    print(f"  PASS cluster (enterprise): {cluster}")


def test_top_entries():
    entries = _sample_entries()
    top = SyntheticReportGenerator._top_entries(entries, n=3)
    assert len(top) == 3
    assert top[0]["id"] == "001"
    assert top[0]["score"] == 76.5
    print(f"  PASS top: #{top[0]['id']} = {top[0]['score']}%")


def test_skill_gaps():
    entries = _sample_entries()
    gaps = SyntheticReportGenerator._compute_skill_gaps(entries)
    assert "Kubernetes" in gaps
    assert gaps["Kubernetes"] == 2
    print(f"  PASS gaps: {gaps}")


def test_direct_matches():
    entries = _sample_entries()
    dm = SyntheticReportGenerator._compute_direct_matches(entries)
    assert dm.get("IoT") == 2
    assert dm.get("Python") == 2
    print(f"  PASS direct_matches: {dm}")


def test_clusters_full():
    entries = _sample_entries()
    clusters = SyntheticReportGenerator._compute_clusters(entries)
    assert "industrial_automation_core" in clusters
    assert "enterprise_it" in clusters
    assert "ai_ml_hype" in clusters
    total = sum(c["count"] for c in clusters.values())
    assert total == len(entries)
    print(f"  PASS clusters: {len(clusters)} groups, {total} entries")


def test_full_generate():
    entries = _sample_entries()
    with tempfile.TemporaryDirectory() as td:
        gen = SyntheticReportGenerator(td)

        md_path, json_path = gen.generate(entries)

        assert md_path.exists()
        assert json_path.exists()

        md_text = md_path.read_text(encoding="utf-8")
        assert "Přehledová statistika" in md_text
        assert "Tech Stack Frequency Matrix" in md_text
        assert "Signal-to-Noise Ratio" in md_text
        assert "Mismatch dimenze" in md_text
        assert "Klastry a patterny" in md_text
        assert "Skill Gaps & CV Optimization" in md_text
        assert "Top 10 nabídek" in md_text
        assert "Závěr a doporučení" in md_text

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "_meta" in data
        assert "overview" in data
        assert "skill_frequency" in data
        assert "signal_to_noise" in data
        assert "mismatch_frequency" in data
        assert "clusters" in data
        assert "top_entries" in data
        assert "skill_gaps" in data
        assert "direct_matches" in data
        assert data["overview"]["total"] == 5

        print(f"  PASS full: MD={md_path.name}, JSON={json_path.name}")


def test_generate_empty():
    with tempfile.TemporaryDirectory() as td:
        gen = SyntheticReportGenerator(td)
        md_path, json_path = gen.generate([])
        assert md_path.exists()
        assert json_path.exists()
        md_text = md_path.read_text(encoding="utf-8")
        assert "No data" in md_text
        print("  PASS empty dataset")


def test_compute_stats():
    entries = _sample_entries()
    gen = SyntheticReportGenerator()
    stats = gen._compute_stats(entries)
    assert stats["total"] == 5
    assert stats["precision_pct"] == 20.0
    assert abs(stats["mean_score"] - 59.0) < 0.1
    print(f"  PASS stats: mean={stats['mean_score']}, precision={stats['precision_pct']}%")


if __name__ == "__main__":
    import sys

    tests = [
        ("verdict_distribution", test_verdict_distribution),
        ("scores", test_scores),
        ("skill_frequency", test_skill_frequency),
        ("snr", test_snr),
        ("mismatch_frequency", test_mismatch_frequency),
        ("cluster_industrial", test_cluster_detection_industrial),
        ("cluster_ai", test_cluster_detection_ai),
        ("cluster_enterprise", test_cluster_detection_enterprise),
        ("top_entries", test_top_entries),
        ("skill_gaps", test_skill_gaps),
        ("direct_matches", test_direct_matches),
        ("clusters_full", test_clusters_full),
        ("full_generate", test_full_generate),
        ("generate_empty", test_generate_empty),
        ("compute_stats", test_compute_stats),
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
