"""One-time migration: dedup 55 entries -> 27 unique (one per LinkedIn saved job).

- Matches DB entries to current LinkedIn tracker jobs by title+company
- Keeps the latest entry per job (prefers manual analysis over auto-scored)
- Adds linkedin_job_id to metadata
- Renumbers IDs with zero-padding (001-027)
- Rewrites both metadata.json and agregovany_report.md
"""

import json
import re
import shutil
from datetime import date
from pathlib import Path

KB_DIR = Path(
    r"C:\Users\PC\Documents\Repozitar_Dev\_github\B2B-Knowledge-Base\02_ANALÝZY\00_linkedin"
)

VERDICT_ICON = {
    "SLEDOVAT": "\U0001f7e2",
    "MEDIUM": "\U0001f7e1",
    "HRANICNI": "\U0001f7e1",
    "NESLEDOVAT": "\U0001f534",
}

EROI_LABEL = {
    "SLEDOVAT": "Vysoká",
    "MEDIUM": "Střední",
    "HRANICNI": "Nízká",
    "NESLEDOVAT": "Kriticky nízká",
}


# ── LinkedIn tracker jobs (title, company, linkedin_job_id) ────────
TRACKER_JOBS = [
    ("TECHNICKÝ PRACOVNÍK PŘÍPRAVY STROJNÍ VÝROBY", "Zakládání staveb", "4354336186"),
    ("Technical Test Engineer / Automation Engineer – SIMATIC IPC", "Siemens", "4418809922"),
    ("Operátor/ka CNC soustruhů", "Katring", "4412855971"),
    ("Vývojář/ka embedded nástrojů a knihoven - C, Python", "Siemens", "4428060844"),
    ("Light Automation Specialist", "Desoutter Tools", "4430450329"),
    ("Trainee/Project Support", "ABB", "4432796957"),
    ("Machine Learning & AI Developer", "Aon", "4408775531"),
    ("IAM Integration Engineer", "N-iX", "4437142473"),
    ("Systémový inženýr RAM/LCC - lokomotivy", "Siemens", "4436064578"),
    ("Solutions Architect - AI & Data Integration", "Deutsche Börse", "4436246101"),
    ("LOGISTICS & SYSTEM ARCHITECT / INTEGRATOR", "MSM GROUP", "4435589028"),
    ("AI / ML / LLM Research Engineer", "Sourcein", "4432613117"),
    ("Automotive CI/CD Engineer (DevOps)", "Digiteq Automotive", "4426045900"),
    ("Lighting R&D Engineer", "Bomma", "4434993470"),
    ("AI Integrator / AI Engineer", "TD SYNNEX", "4431502244"),
    ("VÝVOJÁŘ/VÝVOJÁŘKA NÁSTROJŮ OPTIMALIZACE", "ČEZ", "4431087594"),
    ("PLC Software Engineer", "Sécheron SA", "4426619375"),
    ("Automation Systems Engineer IoT", "Resideo", "4410985508"),
    ("Prototypový technik", "Valeo", "4411284048"),
    ("System Integration Engineer", "Thermo Fisher Scientific", "4424851316"),
    # Pages 2-3 jobs (no LinkedIn job IDs available from scrape):
    ("Zakládání staveb, a.s.", None, None),  # same as #1
    ("Siemens", None, None),  # matches multiple
]


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def match_entry(tracker_title: str, tracker_company: str | None, entry: dict) -> int:
    """Score match between a tracker job and a DB entry (higher=better)."""
    score = 0
    entry_title = normalize(entry.get("title", ""))
    entry_company = normalize(str(entry.get("company", {}).get("industry", "")))

    t_norm = normalize(tracker_title)
    c_norm = normalize(tracker_company) if tracker_company else ""

    # Exact title match
    if entry_title == t_norm:
        score += 10
    # Title contained in each other
    elif t_norm in entry_title or entry_title in t_norm:
        score += 5
    # Significant word overlap
    t_words = set(t_norm.split())
    e_words = set(entry_title.split())
    overlap = len(t_words & e_words)
    score += overlap

    # Company match bonuses
    if c_norm and (entry_company == c_norm or c_norm in entry_company or entry_company in c_norm):
        score += 8

    return score


def main():
    metadata_path = KB_DIR / "metadata_stacku.json"
    report_path = KB_DIR / "agregovany_report.md"

    # Backup originals
    shutil.copy2(metadata_path, KB_DIR / "metadata_stacku.json.bak")
    shutil.copy2(report_path, KB_DIR / "agregovany_report.md.bak")
    print("Backups created: metadata_stacku.json.bak, agregovany_report.md.bak")

    # Load current metadata
    with open(metadata_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["entries"]
    print(f"Current entries: {len(entries)}")

    # For each tracker job, find best matching entry
    kept_entries = []
    seen_ids = set()
    unmatched_trackers = []

    for tracker_title, tracker_company, li_job_id in TRACKER_JOBS:
        if li_job_id is None:
            continue  # skip duplicates within tracker

        best_entry = None
        best_score = 0
        best_idx = -1

        for i, entry in enumerate(entries):
            if i in seen_ids:
                continue
            score = match_entry(tracker_title, tracker_company, entry)
            if score > best_score:
                best_score = score
                best_entry = entry
                best_idx = i

        if best_entry and best_score >= 3:
            best_entry["linkedin_job_id"] = li_job_id
            # If multiple entries match the same job, prefer the one with richer data
            # (manual analysis > auto-scored)
            dup = [e for e in kept_entries if e.get("linkedin_job_id") == li_job_id]
            if dup:
                existing = dup[0]
                existing_is_rich = len(existing.get("domain", {}).get("primary", "") or "") > 0
                new_is_rich = len(best_entry.get("domain", {}).get("primary", "") or "") > 0
                if new_is_rich and not existing_is_rich:
                    kept_entries.remove(existing)
                    kept_entries.append(best_entry)
                    seen_ids.add(best_idx)
            else:
                kept_entries.append(best_entry)
                seen_ids.add(best_idx)
        else:
            unmatched_trackers.append((tracker_title, tracker_company, li_job_id))

    print(f"Matched entries: {len(kept_entries)}")
    print(f"Unmatched tracker jobs: {len(unmatched_trackers)}")
    for t, c, li in unmatched_trackers:
        print(f"  - {t} @ {c} (ID: {li})")

    # Also check for remaining unmatched entries
    orphan_ids = set(range(len(entries))) - seen_ids
    print(f"Orphaned DB entries (removed): {len(orphan_ids)}")
    for i in sorted(orphan_ids):
        e = entries[i]
        print(f"  - #{e['id']}: {e.get('title', '?')}")

    # Renumber with zero-padding
    kept_entries.sort(key=lambda e: e.get("date", ""))
    for new_id, entry in enumerate(kept_entries, 1):
        entry["id"] = f"{new_id:03d}"

    # Write cleaned metadata
    data["entries"] = kept_entries
    data["_meta"]["schema_version"] = "1.1"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nCleaned metadata written: {len(kept_entries)} entries")

    # ── Rebuild agregovany_report.md ────────────────────────────────
    lines = []
    lines.append("# Agregovaný report — LinkedIn nabídky")
    lines.append("")
    lines.append(f"**Autor profilu:** Ondřej Soušek — Systems Integrator")
    lines.append(f"**Počet sledovaných leadů:** {len(kept_entries)}")
    lines.append(f"**Poslední aktualizace:** {date.today().isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for entry in kept_entries:
        fid = entry["id"]
        title = entry.get("title", "Unknown")
        company = entry.get("company", {})
        company_name = company.get("industry", "") if isinstance(company, dict) else ""
        industry = company.get("industry", "") if isinstance(company, dict) else ""
        eroi = entry.get("eroi", {})
        score = eroi.get("fit_score_pct", 0)
        verdict = eroi.get("verdict", "NESLEDOVAT")
        mismatch = eroi.get("mismatch_dimensions", [])
        rec = eroi.get("recommendation", "")
        notes = entry.get("notes", "")

        icon = VERDICT_ICON.get(verdict, "\u26aa")
        lines.append(f"## {icon} ZÁZNAM #{fid} — {title} @ {company_name}")
        lines.append(f"**Datum:** {entry.get('date', 'N/A')}")
        lines.append(f"**EROI verdict:** {verdict} ({score}% fit)")
        lines.append("")
        lines.append("### Analýza pozice")
        lines.append(f"- **Role:** {title}")
        lines.append(f"- **Firma:** {company_name}")
        lines.append("")
        lines.append("### EROI skóre")
        lines.append("| Dimenze | Váha | Skóre | Váženě | Detail |")
        lines.append("|---------|------|-------|--------|--------|")

        # Check if this entry has dimension data (rich) or not (minimal)
        tech_stack = entry.get("tech_stack", {})
        overlap = tech_stack.get("overlap_with_author", {})
        direct_match = overlap.get("direct_match", [])
        partial_match = overlap.get("partial_match", [])
        no_match = overlap.get("no_match", [])

        # Minimal format
        lines.append(f"| domain | 35% | N/A | N/A | — |")
        lines.append(f"| tech | 25% | N/A | N/A | — |")
        lines.append(f"| role | 20% | N/A | N/A | — |")
        lines.append(f"| growth | 10% | N/A | N/A | — |")
        lines.append(f"| formal | 5% | N/A | N/A | — |")
        lines.append(f"| location | 5% | N/A | N/A | — |")
        lines.append(f"| **Celkem** | **100%** | | **{score}%** | **{verdict}** |")
        lines.append("")

        if direct_match or partial_match or no_match:
            lines.append("### Skill match")
            for s in direct_match:
                lines.append(f"- **{s}**: direct_match")
            for s in partial_match:
                lines.append(f"- **{s}**: partial_match")
            for s in no_match:
                lines.append(f"- **{s}**: no_match")
            lines.append("")

        if mismatch:
            lines.append(f"**Kritické mismatch:** {', '.join(mismatch)}")
            lines.append("")

        if rec:
            lines.append(f"**Doporučení:** {rec}")
        if notes:
            lines.append(f"**Poznámka:** {notes}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Souhrnná tabulka
    lines.append("## Souhrnná statistika")
    lines.append("")
    sledovat = sum(1 for e in kept_entries if e.get("eroi", {}).get("verdict") == "SLEDOVAT")
    medium = sum(1 for e in kept_entries if e.get("eroi", {}).get("verdict") == "MEDIUM")
    hranicni = sum(1 for e in kept_entries if e.get("eroi", {}).get("verdict") == "HRANICNI")
    nesledovat = sum(1 for e in kept_entries if e.get("eroi", {}).get("verdict") == "NESLEDOVAT")
    lines.append(f"- 🟢 SLEDOVAT: {sledovat}")
    lines.append(f"- 🟡 MEDIUM: {medium}")
    lines.append(f"- 🟡 HRANIČNÍ: {hranicni}")
    lines.append(f"- 🔴 NESLEDOVAT: {nesledovat}")
    lines.append("")

    report_text = "\n".join(lines)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(
        f"Report rebuilt: {len(kept_entries)} entries, "
        f"{sledovat} SLEDOVAT, {medium} MEDIUM, "
        f"{hranicni} HRANIČNÍ, {nesledovat} NESLEDOVAT"
    )


if __name__ == "__main__":
    main()
