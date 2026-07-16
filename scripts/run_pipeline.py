"""Full pipeline: scrape saved jobs → EROI score → KB write-back.
Logs all errors, warnings, anomalies to docs/ for audit."""

import argparse
import asyncio
import json
import logging
import random
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPORT_DIR = Path(__file__).resolve().parent.parent / "docs"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("pipeline")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LinkedIn EROI pipeline")
    p.add_argument("--limit", type=int, default=0, help="Max jobs to process (0 = all)")
    p.add_argument("--config", type=str, default="", help="Path to YAML config file")
    p.add_argument("--profile", type=str, default="default", help="Analysis profile name")
    p.add_argument("--skip-existing", action="store_true", help="Skip jobs already in KB metadata")
    p.add_argument("--fast", action="store_true", help="Reduced delays [1,3]s, no fingerprint")
    return p.parse_args()


ARGS = parse_args()

report: dict[str, Any] = {
    "test_name": "Full EROI pipeline — scrape → score → KB write",
    "timestamp": datetime.now().isoformat(),
    "date": date.today().isoformat(),
    "status": "unknown",
    "phases": {},
    "errors": [],
    "warnings": [],
    "anomalies": [],
    "per_job": [],
    "summary": {},
}


def log_phase(name: str, data: dict) -> None:
    report["phases"][name] = data


def log_error(phase: str, msg: str, detail: str = "") -> None:
    report["errors"].append({"phase": phase, "message": msg, "detail": detail})
    logger.error("%s: %s | %s", phase, msg, detail)


def log_warning(phase: str, msg: str, detail: str = "") -> None:
    report["warnings"].append({"phase": phase, "message": msg, "detail": detail})
    logger.warning("%s: %s | %s", phase, msg, detail)


def log_anomaly(phase: str, msg: str, detail: str = "") -> None:
    report["anomalies"].append({"phase": phase, "message": msg, "detail": detail})
    logger.warning("ANOMALY %s: %s | %s", phase, msg, detail)


def save_report() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_human_report() -> Path:
    lines = []
    lines.append(f"# Pipeline Report — {report['date']}")
    lines.append(f"**Status:** {report['status']}")
    lines.append(f"**Duration:** {report['summary'].get('total_duration_seconds', '?')}s")
    lines.append("")
    lines.append("## Phases")
    for name, data in report.get("phases", {}).items():
        status = data.get("status", "?")
        lines.append(f"- **{name}**: {status}")
    lines.append("")
    lines.append("## Summary")
    for k, v in report.get("summary", {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    if report.get("errors"):
        lines.append(f"## Errors ({len(report['errors'])})")
        for e in report["errors"]:
            lines.append(f"- [{e['phase']}] {e['message']}: {e['detail']}")
    if report.get("anomalies"):
        lines.append(f"## Anomalies ({len(report['anomalies'])})")
        for a in report["anomalies"]:
            lines.append(f"- [{a['phase']}] {a['message']}: {a['detail']}")
    if report.get("warnings"):
        lines.append(f"## Warnings ({len(report['warnings'])})")
        for w in report["warnings"]:
            lines.append(f"- [{w['phase']}] {w['message']}: {w['detail']}")
    lines.append("")
    lines.append("## Per-job results")
    for job in report.get("per_job", []):
        icon = {"SLEDOVAT": "🟢", "MEDIUM": "🟡", "HRANICNI": "🟡", "NESLEDOVAT": "🔴"}.get(
            job.get("verdict", ""), "⚪"
        )
        lines.append(
            f"- {icon} **{job.get('job_id', '?')}** {job.get('title', '?')}"
            f" @ {job.get('company', '?')}"
            f" → {job.get('score', '?')}% ({job.get('verdict', '?')})"
            f" [{'⚠️' if job.get('error') else '✅'}]"
        )
        if job.get("error"):
            lines.append(f"  - ERROR: {job['error']}")
        if job.get("warnings"):
            for w in job["warnings"]:
                lines.append(f"  - WARN: {w}")

    path = REPORT_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> None:
    global report
    t0 = time.time()

    logger.info("=== PIPELINE START ===")
    log_phase("init", {"status": "started"})

    # Load config (always — uses defaults if no file)
    from linkedin_mcp_custom.config import AppConfig, set_active_config
    from linkedin_mcp_custom.analysis.config import sync_from_active_config

    cfg = AppConfig.load(ARGS.config or None)
    profile_name = ARGS.profile
    set_active_config(cfg, profile_name)
    sync_from_active_config()

    if ARGS.config:
        logger.info("Loaded config from %s (profile: %s)", ARGS.config, profile_name)
    else:
        logger.info("Using default config (profile: %s)", profile_name)

    # --fast override: reduce delays, disable fingerprint
    if ARGS.fast:
        cfg.runtime.delay_range = [1.0, 3.0]
        cfg.runtime.fingerprint_mix = False
        logger.info("FAST mode: delay_range=%s, fingerprint=%s", cfg.runtime.delay_range, cfg.runtime.fingerprint_mix)

    log_phase("config", {
        "status": "ok",
        "user": cfg.user,
        "profile": profile_name,
        "max_pages": cfg.source.max_pages,
        "delay_range": cfg.runtime.delay_range,
        "page_timeout_ms": cfg.runtime.page_timeout_ms,
        "heartbeat": cfg.runtime.session_heartbeat,
        "fingerprint_mix": cfg.runtime.fingerprint_mix,
    })

    max_pages = cfg.source.max_pages
    delay_range = cfg.runtime.delay_range
    heartbeat_interval = cfg.runtime.session_heartbeat
    use_fingerprint = cfg.runtime.fingerprint_mix

    job_ids: list[str] = []
    eroi_results: list[dict] = []
    kb_writer = None
    success_count = 0
    fail_count = 0
    skip_count = 0
    scrape_duration = 0

    try:
        from linkedin_mcp_custom.core import (
            AuthenticationError,
            close_browser,
            ensure_authenticated,
            get_or_create_browser,
        )
        from linkedin_mcp_custom.scraping import LinkedInExtractor

        # ── Phase 1: Browser init ──
        log_phase("browser_init", {"status": "started"})
        logger.info("Opening browser...")
        context = await get_or_create_browser(headless=cfg.runtime.headless)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()
        log_phase("browser_init", {"status": "ok"})
        logger.info("Browser opened")

        # ── Phase 2: Auth check ──
        log_phase("auth", {"status": "checking"})
        try:
            await ensure_authenticated(page)
            logger.info("Auth OK")
            log_phase("auth", {"status": "ok"})
        except AuthenticationError as e:
            log_error("auth", "Authentication failed", str(e))
            log_phase("auth", {"status": "failed", "error": str(e)})
            report["status"] = "auth_failed"
            save_report()
            return
        except Exception as e:
            log_error("auth", "Auth check exception", f"{e}\n{traceback.format_exc()}")
            log_phase("auth", {"status": "failed", "error": str(e)})
            report["status"] = "auth_failed"
            save_report()
            return

        extractor = LinkedInExtractor(page)

        # ── Phase 3: Scrape saved jobs ──
        log_phase("scrape_saved", {"status": "started"})
        t1 = time.time()
        try:
            saved = await extractor.scrape_saved_jobs(max_pages=max_pages)
        except Exception as e:
            log_error("scrape_saved", "Scrape saved jobs failed", f"{e}\n{traceback.format_exc()}")
            log_phase("scrape_saved", {"status": "failed", "error": str(e)})
            report["status"] = "scrape_failed"
            save_report()
            return
        t2 = time.time()
        scrape_duration = round(t2 - t1, 2)

        job_ids = saved.get("job_ids", [])
        sections = saved.get("sections", {})
        section_errors = saved.get("section_errors", {})

        log_phase(
            "scrape_saved",
            {
                "status": "ok",
                "duration_seconds": scrape_duration,
                "job_ids_count": len(job_ids),
                "job_ids": job_ids,
                "has_sections": bool(sections),
                "section_errors": section_errors,
            },
        )

        if section_errors:
            for sname, serr in section_errors.items():
                log_error("scrape_saved", f"Section error: {sname}", serr)

        if not job_ids:
            log_error("scrape_saved", "No job IDs found", "scrape returned empty job_ids list")
            report["status"] = "no_jobs"
            save_report()
            return

        # Dedup check
        unique_ids = list(dict.fromkeys(job_ids))
        if len(unique_ids) != len(job_ids):
            dup_count = len(job_ids) - len(unique_ids)
            log_anomaly(
                "scrape_saved",
                f"Dedup removed {dup_count} duplicate job IDs",
                f"Before: {len(job_ids)}, After: {len(unique_ids)}",
            )
            job_ids = unique_ids

        logger.info("Found %d unique job IDs to analyze", len(job_ids))
        log_phase("scrape_saved", {"unique_job_ids": len(job_ids)})

        # Apply limit (newest jobs first — LinkedIn returns newest first)
        if ARGS.limit > 0 and len(job_ids) > ARGS.limit:
            job_ids = job_ids[: ARGS.limit]
            logger.info("Testing mode: limiting to %d jobs", ARGS.limit)

        # Skip jobs already in KB (--skip-existing)
        skipped_count = 0
        if ARGS.skip_existing:
            try:
                kb_meta_path = (
                    Path.home()
                    / "Documents"
                    / "Repozitar_Dev"
                    / "_github"
                    / "B2B-Knowledge-Base"
                    / "02_ANALÝZY"
                    / "00_linkedin"
                    / "metadata_stacku.json"
                )
                if kb_meta_path.exists():
                    existing_raw = json.loads(kb_meta_path.read_text(encoding="utf-8"))
                    existing_ids = {
                        e.get("linkedin_job_id")
                        for e in existing_raw.get("entries", [])
                        if e.get("linkedin_job_id")
                    }
                    before = len(job_ids)
                    job_ids = [jid for jid in job_ids if jid not in existing_ids]
                    skipped_count = before - len(job_ids)
                    logger.info(
                        "Skip-existing: %d already in KB, %d to scrape",
                        skipped_count,
                        len(job_ids),
                    )
                    if skipped_count > 0:
                        log_phase(
                            "skip_existing",
                            {
                                "skipped": skipped_count,
                                "remaining": len(job_ids),
                            },
                        )
                else:
                    logger.info("No KB metadata found, skipping skip-existing check")
            except Exception as e:
                log_warning("skip_existing", "Failed to check KB metadata", str(e))

        # ── Phase 4: Init KB writer ──
        log_phase("kb_init", {"status": "started"})
        try:
            from linkedin_mcp_custom.analysis.kb_writer import KBWriter
            from linkedin_mcp_custom.analysis.scorer import score_job_from_text
            from linkedin_mcp_custom.analysis.schemas import JobFeatures

            kb_writer = KBWriter()
            log_phase("kb_init", {"status": "ok", "report_path": str(kb_writer.report_path)})
        except Exception as e:
            log_error("kb_init", "KB writer init failed", f"{e}\n{traceback.format_exc()}")
            log_phase("kb_init", {"status": "failed", "error": str(e)})
            report["status"] = "kb_init_failed"
            save_report()
            return

        # ── Phase 5: Per-job scrape + score + write ──
        log_phase("per_job", {"status": "started", "total": len(job_ids)})
        t3 = time.time()

        # P1: Session heartbeat interval (from config)
        last_heartbeat = 0

        for idx, jid in enumerate(job_ids):
            # P1: Session heartbeat — refresh auth before LinkedIn invalidates
            if idx > 0 and (idx - last_heartbeat) >= heartbeat_interval:
                try:
                    await ensure_authenticated(page)
                    last_heartbeat = idx
                    logger.info("Session heartbeat OK at job %d/%d", idx + 1, len(job_ids))
                except AuthenticationError as e:
                    log_error("per_job", f"Session heartbeat failed at job {idx+1}", str(e))
                    report["status"] = "auth_failed"
                    break
                except Exception as e:
                    log_warning("per_job", f"Session heartbeat warning at job {idx+1}", str(e))

            # P0: Random delay between jobs (from config — anti-bot)
            if idx > 0:
                delay = random.uniform(delay_range[0], delay_range[1])
                logger.debug("Anti-bot delay: %.1fs", delay)
                await asyncio.sleep(delay)

            job_start = time.time()
            job_entry: dict[str, Any] = {
                "job_id": jid,
                "index": idx + 1,
                "total": len(job_ids),
                "title": "",
                "company": "",
                "score": None,
                "verdict": None,
                "duration_seconds": None,
                "error": None,
                "warnings": [],
                "anomalies": [],
            }

            try:
                logger.info("[%d/%d] Processing job %s...", idx + 1, len(job_ids), jid)

                details = await extractor.scrape_job(jid)
                sections_dict = details.get("sections", {})
                raw_text = sections_dict.get("job_posting", "")
                title = details.get("job_title", sections_dict.get("job_title", ""))
                company = details.get("company", sections_dict.get("company", ""))
                location = details.get("location", sections_dict.get("location", ""))

                job_entry["title"] = title
                job_entry["company"] = company

                section_errs = details.get("section_errors", {})
                if section_errs:
                    for sname, serr in section_errs.items():
                        msg = f"Section error [{sname}]: {serr}"
                        job_entry["warnings"].append(msg)
                        log_warning(f"job_{jid}", msg)

                if not raw_text:
                    msg = "No job posting text extracted (empty or rate-limited)"
                    job_entry["error"] = msg
                    log_error(f"job_{jid}", msg, f"title={title}, company={company}")
                    fail_count += 1
                    job_entry["duration_seconds"] = round(time.time() - job_start, 2)
                    report["per_job"].append(job_entry)
                    continue

                # EROI score
                try:
                    eroi = score_job_from_text(
                        job_id=jid,
                        job_title=title,
                        company=company,
                        raw_text=raw_text,
                        location=location,
                    )
                except Exception as e:
                    msg = f"EROI scoring failed: {e}"
                    job_entry["error"] = msg
                    log_error(f"job_{jid}", msg, traceback.format_exc())
                    fail_count += 1
                    job_entry["duration_seconds"] = round(time.time() - job_start, 2)
                    report["per_job"].append(job_entry)
                    continue

                job_entry["score"] = eroi.total_score
                job_entry["verdict"] = eroi.verdict
                job_entry["dimensions"] = {
                    d.name: f"{d.score}% ({d.detail})" for d in eroi.dimensions
                }
                job_entry["skill_gaps"] = [f"{g.skill}: {g.match}" for g in eroi.skill_gaps]
                job_entry["mismatch_dimensions"] = eroi.mismatch_dimensions

                # KB write-back
                try:
                    write_result = kb_writer.write_all(eroi, raw_text, linkedin_job_id=jid)
                    job_entry["kb_write"] = write_result
                    logger.info(
                        "  KB #%s: %s @ %s → %s%% (%s) [%s]",
                        write_result.get("entry_id", "?"),
                        title,
                        company,
                        eroi.total_score,
                        eroi.verdict,
                        "updated" if write_result.get("updated") else "new",
                    )
                    success_count += 1
                except Exception as e:
                    msg = f"KB write-back failed: {e}"
                    job_entry["error"] = msg
                    log_error(f"job_{jid}", msg, traceback.format_exc())
                    fail_count += 1
                    job_entry["duration_seconds"] = round(time.time() - job_start, 2)
                    report["per_job"].append(job_entry)
                    continue

            except asyncio.TimeoutError:
                msg = f"Job {jid} timed out"
                job_entry["error"] = msg
                log_error(f"job_{jid}", msg)
                fail_count += 1
            except Exception as e:
                msg = f"Unhandled job error: {e}"
                job_entry["error"] = msg
                log_error(f"job_{jid}", msg, traceback.format_exc())
                fail_count += 1

            job_entry["duration_seconds"] = round(time.time() - job_start, 2)
            report["per_job"].append(job_entry)

        t4 = time.time()
        job_phase_duration = round(t4 - t3, 2)

        log_phase(
            "per_job",
            {
                "status": "done",
                "duration_seconds": job_phase_duration,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "total": len(job_ids),
            },
        )

        # ── Phase 6: Git commit ──
        if kb_writer and success_count > 0:
            log_phase("git_commit", {"status": "started"})
            try:
                commit_msg = f"[ANALÝZY] pipeline: {success_count} jobs EROI scored ({date.today().isoformat()})"
                kb_writer.commit_changes(commit_msg)
                log_phase("git_commit", {"status": "ok", "message": commit_msg})
            except Exception as e:
                log_error("git_commit", "Git commit failed", str(e))
                log_phase("git_commit", {"status": "failed", "error": str(e)})
        elif success_count == 0:
            log_warning("git_commit", "Skipping commit: 0 successful jobs")

        # ── Phase 7: Synthetic report (P3) ──
        if success_count > 0:
            log_phase("synthetic_report", {"status": "started"})
            try:
                from linkedin_mcp_custom.analysis.report_generator import (
                    SyntheticReportGenerator,
                )
                gen = SyntheticReportGenerator()
                md_path, json_path = gen.generate()
                log_phase(
                    "synthetic_report",
                    {
                        "status": "ok",
                        "md_path": str(md_path),
                        "json_path": str(json_path),
                    },
                )
                logger.info(
                    "Synthetic report generated:\n  MD:  %s\n  JSON: %s",
                    md_path,
                    json_path,
                )
            except Exception as e:
                log_error("synthetic_report", "Report generation failed", str(e))
                log_phase("synthetic_report", {"status": "failed", "error": str(e)})

    except Exception as e:
        log_error("global", "Unhandled pipeline exception", f"{e}\n{traceback.format_exc()}")
        logger.exception("FATAL")
        report["status"] = "crashed"
    finally:
        try:
            from linkedin_mcp_custom.core import close_browser

            await close_browser()
            logger.info("Browser closed")
        except Exception as e:
            log_warning("cleanup", "Browser close failed", str(e))

    td = round(time.time() - t0, 2)

    verdict_groups: dict[str, int] = {}
    for job in report["per_job"]:
        v = job.get("verdict") or "ERROR"
        verdict_groups[v] = verdict_groups.get(v, 0) + 1

    report["summary"] = {
        "total_duration_seconds": td,
        "scrape_duration_seconds": report["phases"]
        .get("scrape_saved", {})
        .get("duration_seconds", 0),
        "per_job_duration_seconds": report["phases"].get("per_job", {}).get("duration_seconds", 0),
        "job_ids_found": len(job_ids),
        "jobs_success": success_count,
        "jobs_failed": fail_count,
        "errors_count": len(report["errors"]),
        "warnings_count": len(report["warnings"]),
        "anomalies_count": len(report["anomalies"]),
        "verdict_distribution": verdict_groups,
    }

    has_fatal = bool(report.get("status") in ("crashed", "auth_failed", "scrape_failed"))
    has_errors = fail_count > 0
    report["status"] = (
        "ok" if (success_count > 0 and not has_fatal) else "partial" if has_errors else "failed"
    )

    json_path = save_report()
    md_path = save_human_report()

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"PIPELINE REPORT")
    print(f"{'=' * 60}")
    print(f"Conclusion: {report['status']}")
    print(f"Duration: {td}s total ({scrape_duration}s scrape)")
    print(f"Job IDs found: {len(job_ids)}")
    print(f"Jobs scored: {success_count}")
    print(f"Jobs failed: {fail_count}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    print(f"Anomalies: {len(report['anomalies'])}")
    if verdict_groups:
        print(f"\nVerdicts: {verdict_groups}")
    print(f"\nReports:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print(f"{'=' * 60}\n")

    if report["errors"]:
        print("--- ERRORS ---")
        for e in report["errors"]:
            print(f"  [{e['phase']}] {e['message']}")
    if report["anomalies"]:
        print("--- ANOMALIES ---")
        for a in report["anomalies"]:
            print(f"  [{a['phase']}] {a['message']}")
    if report["warnings"]:
        print("--- WARNINGS ---")
        for w in report["warnings"]:
            print(f"  [{w['phase']}] {w['message']}")


if __name__ == "__main__":
    asyncio.run(main())
