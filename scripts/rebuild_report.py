"""Rebuild agregovany_report.md from backup, preserving rich manual analysis."""

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


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def find_best_block(title: str, blocks: list[tuple[str, str]], min_score: int = 3) -> str | None:
    """Find best matching backup block by title similarity."""
    t_norm = normalize(title)
    t_words = set(t_norm.split())

    best_block = None
    best_score = 0

    for block_id, block_text in blocks:
        # Extract title from block header (## ... ZÁZNAM #[ID] — TITLE @ COMPANY)
        header_match = re.search(r"## . ZÁZNAM #\d+ — (.+?) @", block_text)
        if not header_match:
            continue
        block_title = header_match.group(1)
        b_norm = normalize(block_title)
        b_words = set(b_norm.split())

        overlap = len(t_words & b_words)
        # Bonus for exact match
        if t_norm == b_norm:
            overlap += 20
        # Bonus for one containing the other
        elif t_norm in b_norm or b_norm in t_norm:
            overlap += 10

        if overlap > best_score:
            best_score = overlap
            best_block = block_text

    if best_score >= min_score:
        return best_block
    return None


def main():
    report_path = KB_DIR / "agregovany_report.md"
    meta_path = KB_DIR / "metadata_stacku.json"
    backup_path = KB_DIR / "agregovany_report.md.bak"

    if not backup_path.exists():
        print("ERROR: Backup not found. Run dedup_migration.py first.")
        return

    # Load cleaned metadata
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    entries = meta["entries"]

    # Parse backup report into blocks
    backup_text = backup_path.read_text(encoding="utf-8")
    # Split on ## (start of each section), keep the delimiter
    raw_blocks = re.split(r"^(?=## )", backup_text, flags=re.MULTILINE)
    # Extract entry blocks (ZÁZNAM) with their old IDs
    entry_blocks: list[tuple[str, str]] = []
    for block in raw_blocks:
        m = re.search(r"ZÁZNAM #(\d+)", block)
        if m:
            entry_blocks.append((m.group(1), block))

    print(f"Backup entry blocks: {len(entry_blocks)}")
    print(f"Entries to write: {len(entries)}")

    # ── Build report ────────────────────────────────────────────────
    lines = []
    lines.append("# Agregovaný report — LinkedIn nabídky")
    lines.append("")
    lines.append(
        "**Autor profilu:** Ondřej Soušek — Systems Integrator, formalizace & reverse engineering"
    )
    lines.append(
        "**Workflow:** Každá nová nabídka přidána jako sekce, hodnocena na EROI alokace času."
    )
    lines.append("")

    used_blocks = 0
    generic_entries = 0

    for entry in entries:
        fid = entry["id"]
        title = entry.get("title", "Unknown")
        company = entry.get("company", {})
        company_name = company if isinstance(company, str) else company.get("industry", "")
        score = entry.get("eroi", {}).get("fit_score_pct", 0)
        verdict = entry.get("eroi", {}).get("verdict", "NESLEDOVAT")

        # Find matching backup block
        block = find_best_block(title, entry_blocks, min_score=3)

        if block:
            # Replace old ID with new zero-padded ID
            old_id_match = re.search(r"#(\d+)", block)
            if old_id_match:
                old_id = old_id_match.group(1)
                # Only replace first occurrence (the ZÁZNAM header)
                block = block.replace(f"#{old_id}", f"#{fid}", 1)
                # Also update the summary table row if present
                block = re.sub(r"\| \*\*Celkem\*\*.*?\|\n", "", block)
                # Fix the verdict line if outdated
                block = re.sub(
                    r"\*\*EROI verdict:\*\*.*",
                    f"**EROI verdict:** {verdict} ({score}% fit)",
                    block,
                )
            lines.append(block)
            used_blocks += 1
        else:
            # Generic fallback
            icon = VERDICT_ICON.get(verdict, "\u26aa")
            lines.append(f"\n## {icon} ZÁZNAM #{fid} — {title} @ {company_name}")
            lines.append(f"**Datum:** {entry.get('date', 'N/A')}")
            lines.append(f"**EROI verdict:** {verdict} ({score}% fit)")
            lines.append("")
            lines.append("### EROI skóre")
            lines.append("| Dimenze | Váha | Skóre | Váženě | Detail |")
            lines.append("|---------|------|-------|--------|--------|")
            lines.append(f"| domain | 35% | N/A | N/A | — |")
            lines.append(f"| tech | 25% | N/A | N/A | — |")
            lines.append(f"| role | 20% | N/A | N/A | — |")
            lines.append(f"| growth | 10% | N/A | N/A | — |")
            lines.append(f"| formal | 5% | N/A | N/A | — |")
            lines.append(f"| location | 5% | N/A | N/A | — |")
            lines.append(f"| **Celkem** | **100%** | | **{score}%** | **{verdict}** |")
            lines.append("")
            lines.append("---")
            generic_entries += 1

    # ── Summary section ─────────────────────────────────────────────
    lines.append("\n## Souhrnná statistika\n")
    sledovat = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "SLEDOVAT")
    medium = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "MEDIUM")
    hranicni = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "HRANICNI")
    nesledovat = sum(1 for e in entries if e.get("eroi", {}).get("verdict") == "NESLEDOVAT")
    lines.append(f"- 🟢 SLEDOVAT: {sledovat}")
    lines.append(f"- 🟡 MEDIUM: {medium}")
    lines.append(f"- 🟡 HRANIČNÍ: {hranicni}")
    lines.append(f"- 🔴 NESLEDOVAT: {nesledovat}")
    lines.append("")

    # Summary table
    lines.append("| # | Firma | Role | Fit % | EROI | Verdikt |")
    lines.append("|---|-------|------|-------|------|---------|")
    for entry in entries:
        fid = entry["id"]
        title = entry.get("title", "?")
        company = entry.get("company", {})
        company_name = company if isinstance(company, str) else company.get("industry", "")
        score = entry.get("eroi", {}).get("fit_score_pct", 0)
        verdict = entry.get("eroi", {}).get("verdict", "?")
        icon = VERDICT_ICON.get(verdict, "")
        eroi_label = EROI_LABEL.get(verdict, "")
        lines.append(
            f"| {fid} | {company_name} | {title} | {score}% | {eroi_label} | {icon} {verdict} |"
        )

    report_text = "\n".join(lines)

    # Backup current report before overwriting
    shutil.copy2(report_path, KB_DIR / "agregovany_report.md.curr_bak")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"Report rebuilt: {len(entries)} entries")
    print(f"  Rich blocks reused: {used_blocks}")
    print(f"  Generic fallbacks: {generic_entries}")
    print(f"  {sledovat} SLEDOVAT, {medium} MEDIUM, {hranicni} HRANIČNÍ, {nesledovat} NESLEDOVAT")


if __name__ == "__main__":
    main()
