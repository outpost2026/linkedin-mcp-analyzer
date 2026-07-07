"""Rebuild agregovany_report.md from pipeline JSON report + metadata.
Ensures clean section separation after kb_writer bugfix."""

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

KB_DIR = Path(
    r"C:\Users\PC\Documents\Repozitar_Dev\_github\B2B-Knowledge-Base\02_ANALÝZY\00_linkedin"
)

VERDICT_ICON = {
    "SLEDOVAT": "🟢",
    "MEDIUM": "🟡",
    "HRANICNI": "🟡",
    "NESLEDOVAT": "🔴",
}

EROI_LABEL = {
    "SLEDOVAT": "Vysoká",
    "MEDIUM": "Střední",
    "HRANICNI": "Nízká",
    "NESLEDOVAT": "Kriticky nízká",
}


def load_pipeline_report() -> dict | None:
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    reports = sorted(docs_dir.glob("pipeline_*.json"))
    if not reports:
        print("No pipeline reports found in docs/")
        return None
    latest = reports[-1]
    print(f"Using pipeline report: {latest.name}")
    return json.loads(latest.read_text(encoding="utf-8"))


def load_metadata() -> dict:
    return json.loads(KB_DIR.joinpath("metadata_stacku.json").read_text(encoding="utf-8"))


def format_entry(entry: dict, job_data: dict | None) -> str:
    fid = entry["id"]
    title = entry.get("title", "Unknown")
    company_name = entry.get("company", {}).get("industry", "Unknown")
    score = entry.get("eroi", {}).get("fit_score_pct", 0)
    verdict = entry.get("eroi", {}).get("verdict", "NESLEDOVAT")
    mismatches = entry.get("eroi", {}).get("mismatch_dimensions", [])
    icon = VERDICT_ICON.get(verdict, "⚪")

    lines = []
    lines.append(f"\n## {icon} ZÁZNAM #{fid} — {title} @ {company_name}")
    lines.append(f"**Datum:** {entry.get('date', date.today().isoformat())}")
    lines.append(f"**EROI verdict:** {verdict} ({score}% fit)")
    lines.append("")
    lines.append("### Analýza pozice")
    lines.append(f"- **Role:** {title}")
    lines.append(f"- **Firma:** {company_name}")
    lines.append("")

    # Dimension details from pipeline report (or generic)
    dims = None
    if job_data and job_data.get("dimensions"):
        dims = job_data["dimensions"]

    lines.append("### EROI skóre")
    lines.append("| Dimenze | Váha | Skóre | Váženě | Detail |")
    lines.append("|---------|------|-------|--------|--------|")

    dim_order = ["domain", "tech", "role", "growth", "formal", "location"]
    dim_weights = {
        "domain": 0.35,
        "tech": 0.25,
        "role": 0.20,
        "growth": 0.10,
        "formal": 0.05,
        "location": 0.05,
    }

    total_weighted = 0
    for dim_name in dim_order:
        weight = dim_weights[dim_name]
        if dims and dim_name in dims:
            dim_str = dims[dim_name]
            m = re.match(r"([\d.]+)%", dim_str)
            if m:
                dim_score_val = float(m.group(1))
                detail_part = dim_str.split("(", 1)[1].rstrip(")") if "(" in dim_str else dim_str
                weighted = round(dim_score_val * weight / 100, 1)
                lines.append(
                    f"| {dim_name} | {weight * 100:.0f}% | {dim_score_val:.1f}% | {weighted:.1f}% | {detail_part} |"
                )
                total_weighted += dim_score_val * weight
                continue
        lines.append(f"| {dim_name} | {weight * 100:.0f}% | N/A | N/A | — |")

    lines.append(f"| **Celkem** | **100%** | | **{score:.1f}%** | **{verdict}** |")
    lines.append("")

    # Skill match from metadata
    tech = entry.get("tech_stack", {}).get("overlap_with_author", {})
    direct = tech.get("direct_match", [])
    partial = tech.get("partial_match", [])
    no_match = tech.get("no_match", [])
    all_gaps = direct + partial + no_match
    if all_gaps:
        lines.append("### Skill match")
        for g in all_gaps:
            match_type = (
                "direct_match" if g in direct else "partial_match" if g in partial else "no_match"
            )
            lines.append(f"- **{g}**: {match_type}")
        lines.append("")

    if mismatches:
        lines.append(f"**Kritické mismatch:** {', '.join(mismatches)}")
        lines.append("")

    lines.append(
        f"**Doporučení:** {'Aplikovat — silný lead' if score >= 65 else 'Zvážit aplikaci — střední fit, nutná mitigace gapů' if score >= 50 else 'Hraniční — aplikovat jen pokud zbývající čas' if score >= 40 else 'Nealokovat čas'}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def main():
    pipeline = load_pipeline_report()
    meta = load_metadata()
    entries = meta["entries"]

    # Build per-job lookup from pipeline report (by job_id = linkedin_job_id)
    job_lookup: dict[str, dict] = {}
    if pipeline:
        for job in pipeline.get("per_job", []):
            jid = job.get("job_id", "")
            if jid:
                job_lookup[jid] = job

    # Also build by metadata title+company match
    meta_lookup: dict[str, dict] = {}
    for e in entries:
        title = e.get("title", "")
        company = e.get("company", {}).get("industry", "")
        key = f"{title}|{company}"
        meta_lookup[key] = e

    # Backup current report
    report_path = KB_DIR / "agregovany_report.md"
    if report_path.exists():
        shutil.copy2(report_path, KB_DIR / "agregovany_report.md.pre_rebuild_bak")
        print(f"Backed up old report to agregovany_report.md.pre_rebuild_bak")

    # Build report
    all_lines = []
    all_lines.append("# Agregovaný report — LinkedIn nabídky")
    all_lines.append("")
    all_lines.append(
        "**Autor profilu:** Ondřej Soušek — Systems Integrator, formalizace & reverse engineering"
    )
    all_lines.append(
        "**Workflow:** Každá nová nabídka přidána jako sekce, hodnocena na EROI alokace času."
    )
    all_lines.append("")

    for entry in entries:
        fid = entry["id"]
        title = entry.get("title", "")
        company = entry.get("company", {}).get("industry", "")

        # Find matching pipeline job data
        linkedin_id = entry.get("linkedin_job_id", "")
        job_data = job_lookup.get(linkedin_id, None)

        block = format_entry(entry, job_data)
        all_lines.append(block)

    # Summary section
    all_lines.append("\n## Souhrnná statistika\n")
    sledovat = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "SLEDOVAT")
    medium = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "MEDIUM")
    hranicni = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "HRANICNI")
    nesledovat = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "NESLEDOVAT")
    all_lines.append(f"- 🟢 SLEDOVAT: {sledovat}")
    all_lines.append(f"- 🟡 MEDIUM: {medium}")
    all_lines.append(f"- 🟡 HRANIČNÍ: {hranicni}")
    all_lines.append(f"- 🔴 NESLEDOVAT: {nesledovat}")
    all_lines.append("")
    all_lines.append("| # | Firma | Role | Fit % | EROI | Verdikt |")
    all_lines.append("|---|-------|------|-------|------|---------|")
    for entry in entries:
        fid = entry["id"]
        title = entry.get("title", "?")
        company = entry.get("company", {})
        company_name = company if isinstance(company, str) else company.get("industry", "")
        score = entry.get("eroi", {}).get("fit_score_pct", 0)
        verdict = entry.get("eroi", {}).get("verdict", "?")
        icon = VERDICT_ICON.get(verdict, "")
        eroi_label = EROI_LABEL.get(verdict, "")
        all_lines.append(
            f"| {fid} | {company_name} | {title} | {score}% | {eroi_label} | {icon} {verdict} |"
        )
    all_lines.append("")

    report_text = "\n".join(all_lines)
    report_path.write_text(report_text, encoding="utf-8")

    # Restore summary table from old report if it had better formatting
    print(f"Report rebuilt: {len(entries)} entries")
    print(f"  {sledovat} SLEDOVAT, {medium} MEDIUM, {hranicni} HRANIČNÍ, {nesledovat} NESLEDOVAT")
    print(
        f"  Pipeline job data matched: {sum(1 for e in entries if job_lookup.get(e.get('linkedin_job_id', '')))}/{len(entries)}"
    )


if __name__ == "__main__":
    main()
