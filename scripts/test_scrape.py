"""Test script: scrape saved jobs, log everything, NO analysis.
Creates structured report in docs/."""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent.parent / "docs"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("test_scrape")

report = {
    "test_name": "Scraping pipeline test — Session 4",
    "timestamp": datetime.now().isoformat(),
    "status": "unknown",
    "phases": {},
    "errors": [],
    "warnings": [],
    "anomalies": [],
    "summary": {},
}


def log_phase(name: str, data: dict):
    report["phases"][name] = data


def log_error(phase: str, msg: str, detail: str = ""):
    entry = {"phase": phase, "message": msg, "detail": detail}
    report["errors"].append(entry)
    logger.error("%s: %s | %s", phase, msg, detail)


def log_warning(phase: str, msg: str, detail: str = ""):
    entry = {"phase": phase, "message": msg, "detail": detail}
    report["warnings"].append(entry)
    logger.warning("%s: %s | %s", phase, msg, detail)


def log_anomaly(phase: str, msg: str, detail: str = ""):
    entry = {"phase": phase, "message": msg, "detail": detail}
    report["anomalies"].append(entry)
    logger.warning("ANOMALY %s: %s | %s", phase, msg, detail)


def save_report():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"scrape_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Report saved to %s", path)
    return path


async def main():
    global report
    t0 = time.time()
    logger.info("=== TEST SCRAPE START ===")

    job_ids = []
    page_count = 0
    scrape_duration = 0

    try:
        from linkedin_mcp_custom.core import (
            get_or_create_browser,
            ensure_authenticated,
            close_browser,
        )
        from linkedin_mcp_custom.scraping import LinkedInExtractor

        log_phase("browser_init", {"status": "started"})
        context = await get_or_create_browser(headless=True)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()
        logger.info("Browser opened")
        log_phase("browser_init", {"status": "ok"})

        # Auth check
        log_phase("auth", {"status": "checking"})
        try:
            await ensure_authenticated(page)
            logger.info("Auth OK")
            log_phase("auth", {"status": "ok"})
        except Exception as e:
            log_error("auth", "Authentication failed", str(e))
            log_phase("auth", {"status": "failed", "error": str(e)})
            report["status"] = "auth_failed"
            save_report()
            return

        extractor = LinkedInExtractor(page)
        log_phase("scraping", {"status": "started"})

        t1 = time.time()
        result = await extractor.scrape_saved_jobs()
        t2 = time.time()
        scrape_duration = round(t2 - t1, 2)

        job_ids = result.get("job_ids", [])
        sections = result.get("sections", {})
        errors = result.get("section_errors", {})

        log_phase(
            "scraping",
            {
                "status": "ok",
                "duration_seconds": scrape_duration,
                "job_ids_count": len(job_ids),
                "job_ids": job_ids,
                "has_sections": bool(sections),
                "errors": errors,
            },
        )

        # Analyze results
        if errors:
            for section_name, err_msg in errors.items():
                log_error("scraping", f"Section error: {section_name}", err_msg)

        if job_ids:
            unique = set(job_ids)
            dup_count = len(job_ids) - len(unique)
            if dup_count > 0:
                log_anomaly(
                    "dedup",
                    f"Found {dup_count} duplicate job IDs before dedup",
                    f"Total: {len(job_ids)}, Unique: {len(unique)}",
                )

        # Estimate page count from pagination
        raw_text = sections.get("saved_jobs", "")
        page_count = raw_text.count("PAGE BREAK") + 1 if raw_text else 1
        log_phase("pagination", {"estimated_pages": page_count})

        report["status"] = "ok" if job_ids else "no_results"

    except Exception as e:
        log_error("global", "Unhandled exception", str(e))
        logger.exception("FATAL")
        report["status"] = "crashed"
    finally:
        from linkedin_mcp_custom.core import close_browser

        await close_browser()
        logger.info("Browser closed")

    td = round(time.time() - t0, 2)

    report["summary"] = {
        "total_duration_seconds": td,
        "scrape_duration_seconds": scrape_duration,
        "job_ids_found": len(job_ids),
        "unique_job_ids": len(set(job_ids)) if job_ids else 0,
        "estimated_pages": page_count,
        "errors_count": len(report["errors"]),
        "warnings_count": len(report["warnings"]),
        "anomalies_count": len(report["anomalies"]),
    }

    report["conclusion"] = (
        "PASS"
        if report["status"] == "ok" and len(job_ids) > 0
        else "FAIL"
        if report["status"] in ("crashed", "auth_failed")
        else "PARTIAL"
    )

    saved_path = save_report()

    # Print human readable summary
    print(f"\n{'=' * 60}")
    print(f"SCRAPING TEST REPORT")
    print(f"{'=' * 60}")
    print(f"Conclusion: {report['conclusion']}")
    print(f"Status: {report['status']}")
    print(f"Duration: {scrape_duration}s scrape / {td}s total")
    print(f"Job IDs: {len(job_ids)} ({len(set(job_ids))} unique)")
    print(f"Pages: ~{page_count}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    print(f"Anomalies: {len(report['anomalies'])}")
    print(f"Report: {saved_path}")
    print(f"{'=' * 60}")

    # Show errors/warnings/anomalies inline
    if report["errors"]:
        print("\n--- ERRORS ---")
        for e in report["errors"]:
            print(f"  [{e['phase']}] {e['message']}: {e['detail']}")
    if report["anomalies"]:
        print("\n--- ANOMALIES ---")
        for a in report["anomalies"]:
            print(f"  [{a['phase']}] {a['message']}: {a['detail']}")
    if report["warnings"]:
        print("\n--- WARNINGS ---")
        for w in report["warnings"]:
            print(f"  [{w['phase']}] {w['message']}: {w['detail']}")

    print(f"\nJob IDs: {job_ids}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
