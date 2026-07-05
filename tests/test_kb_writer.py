"""Test KB writer formatting and ID generation."""

import json
import tempfile
from pathlib import Path

from linkedin_mcp_custom.analysis.scorer import score_job_from_text
from linkedin_mcp_custom.analysis.kb_writer import KBWriter


def _sample_eroi() -> tuple:
    text = """
    Test Engineer. Industrial automation, PLC, Python, CI/CD.
    Manufacturing, factory automation. Prague office.
    Bachelor's degree or equivalent.
    """
    eroi = score_job_from_text(
        job_id="999",
        job_title="Test Engineer",
        company="Siemens",
        raw_text=text,
        location="Praha",
    )
    return eroi, text


def test_get_next_id():
    """Should return 19 (next after 18) from existing metadata."""
    writer = KBWriter()
    if writer.metadata_path.exists():
        next_id = writer.get_next_id()
        assert next_id >= 19, f"Expected >= 19, got {next_id}"
        print(f"  PASS next_id: {next_id}")
    else:
        writer2 = KBWriter(str(tempfile.mkdtemp()))
        assert writer2.get_next_id() == 1
        print("  PASS next_id: 1 (no metadata file)")


def test_format_entry_md():
    """MD output should contain key fields."""
    eroi, text = _sample_eroi()
    with tempfile.TemporaryDirectory() as td:
        writer = KBWriter(td)
        block = writer._format_entry_md(eroi, text)
        assert "Test Engineer" in block
        assert "Siemens" in block
        assert "EROI verdict" in block
        assert "Siemens" in block
        print(f"  PASS MD format ({len(block)} chars)")


def test_format_entry_json():
    """JSON output should have all expected keys."""
    eroi, text = _sample_eroi()
    with tempfile.TemporaryDirectory() as td:
        writer = KBWriter(td)
        entry = writer._format_entry_json(eroi)
        assert entry["id"] == "999"
        assert entry["title"] == "Test Engineer"
        assert entry["company"]["type"] is None
        assert entry["eroi"]["verdict"] in (
            "SLEDOVAT",
            "MEDIUM",
            "HRANICNI",
            "NESLEDOVAT",
        )
        print(
            f"  PASS JSON format: {entry['eroi']['verdict']} @ {entry['eroi']['fit_score_pct']}%"
        )


def test_write_all_no_commit():
    """Write to temp dir without git commit."""
    eroi, text = _sample_eroi()
    with tempfile.TemporaryDirectory() as td:
        writer = KBWriter(td)
        result = writer.write_all(eroi, text)
        assert result["status"] == "ok"
        report = Path(result["report_path"])
        meta = Path(result["metadata_path"])
        assert report.exists(), "Report not created"
        assert meta.exists(), "Metadata not created"
        report_text = report.read_text(encoding="utf-8")
        assert "Test Engineer" in report_text
        assert "Siemens" in report_text
        with open(meta) as f:
            data = json.load(f)
        assert len(data["entries"]) >= 1
        print(
            f"  PASS write_all: report={report.stat().st_size}B, meta={len(data['entries'])} entries"
        )


if __name__ == "__main__":
    import sys

    tests = [
        ("get_next_id", test_get_next_id),
        ("format_md", test_format_entry_md),
        ("format_json", test_format_entry_json),
        ("write_all", test_write_all_no_commit),
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
