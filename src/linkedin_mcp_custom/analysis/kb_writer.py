"""KB writer — upsert EROI results to B2B-Knowledge-Base with dedup."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from linkedin_mcp_custom.analysis import normalize as _util_normalize
from linkedin_mcp_custom.analysis.schemas import EROIResult

logger = logging.getLogger(__name__)

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


def _normalize(s: str) -> str:
    """Normalize string for dedup comparison (with diacritics stripping)."""
    return _util_normalize(s)


class KBWriter:
    """Writes EROI analysis results to the B2B-Knowledge-Base with dedup."""

    def __init__(self, kb_path: str | None = None):
        if kb_path is None:
            kb_path = os.path.join(
                os.path.expanduser("~"),
                "Documents",
                "Repozitar_Dev",
                "_github",
                "B2B-Knowledge-Base",
                "02_ANALÝZY",
                "00_linkedin",
            )
        self.linkedin_dir = Path(kb_path)
        self.report_path = self.linkedin_dir / "agregovany_report.md"
        self.metadata_path = self.linkedin_dir / "metadata_stacku.json"
        self._next_id: int | None = None

    def get_next_id(self) -> int:
        if self._next_id is not None:
            self._next_id += 1
            return self._next_id
        max_id = 0
        try:
            with open(self.metadata_path, encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("entries", []):
                eid = entry.get("id", "0")
                if isinstance(eid, str) and eid.isdigit():
                    max_id = max(max_id, int(eid))
        except (FileNotFoundError, json.JSONDecodeError):
            max_id = 0
        self._next_id = max_id + 1
        return max_id + 1

    def _format_id(self, n: int) -> str:
        return f"{n:03d}"

    def _format_entry_md(self, eroi: EROIResult, raw_text: str) -> str:
        icon = VERDICT_ICON.get(eroi.verdict, "⚪")
        fid = self._format_id(int(eroi.job_id))
        lines = []
        lines.append(f"\n## {icon} ZÁZNAM #{fid} — {eroi.job_title} @ {eroi.company}")
        lines.append(f"**Datum:** {date.today().isoformat()}")
        lines.append(f"**EROI verdict:** {eroi.verdict} ({eroi.total_score}% fit)")
        lines.append("")
        lines.append("### Analýza pozice")
        lines.append(f"- **Role:** {eroi.job_title}")
        lines.append(f"- **Firma:** {eroi.company}")
        lines.append("")
        lines.append("### EROI skóre")
        lines.append("| Dimenze | Váha | Skóre | Váženě | Detail |")
        lines.append("|---------|------|-------|--------|--------|")
        for d in eroi.dimensions:
            weighted = round(d.score * d.weight / 100, 1)
            row = (
                f"| {d.name} | {d.weight * 100:.0f}% | {d.score:.1f}%"
                f" | {weighted:.1f}% | {d.detail} |"
            )
            lines.append(row)
        lines.append(
            f"| **Celkem** | **100%** | | **{eroi.total_score:.1f}%** | **{eroi.verdict}** |"
        )
        lines.append("")
        if eroi.skill_gaps:
            lines.append("### Skill match")
            for g in eroi.skill_gaps:
                lines.append(f"- **{g.skill}**: {g.match}")
        lines.append("")
        if eroi.mismatch_dimensions:
            lines.append(f"**Kritické mismatch:** {', '.join(eroi.mismatch_dimensions)}")
        lines.append("")
        lines.append(f"**Doporučení:** {eroi.recommendation}")
        if eroi.notes:
            lines.append(f"**Poznámka:** {eroi.notes}")
        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _format_entry_json(self, eroi: EROIResult, linkedin_job_id: str = "", raw_text: str = "") -> dict[str, Any]:
        skill_gaps = eroi.skill_gaps
        direct_match = [g.skill for g in skill_gaps if g.match == "direct_match"]
        partial_match = [g.skill for g in skill_gaps if g.match == "partial_match"]
        no_match = [g.skill for g in skill_gaps if g.match == "no_match"]
        entry: dict[str, Any] = {
            "id": self._format_id(int(eroi.job_id)),
            "date": date.today().isoformat(),
            "linkedin_job_id": linkedin_job_id,
            "company": {
                "type": None,
                "size_range": None,
                "industry": eroi.company,
            },
            "title": eroi.job_title,
            "role": {
                "category": None,
                "subcategory": None,
                "seniority": None,
                "employment_type": None,
                "location": None,
                "remote_policy": None,
            },
            "tech_stack": {
                "overlap_with_author": {
                    "direct_match": direct_match,
                    "partial_match": partial_match,
                    "no_match": no_match,
                }
            },
            "domain": {
                "primary": None,
                "secondary": None,
                "specific": None,
            },
            "formal_requirements": {
                "years_experience_min": None,
                "education": None,
                "certifications": None,
                "languages": [],
                "other": [],
            },
            "eroi": {
                "fit_score_pct": eroi.total_score,
                "conversion_probability": None,
                "estimated_value_monthly_czk": None,
                "estimated_prep_cost_hours": None,
                "verdict": eroi.verdict,
                "critical_mismatch": len(eroi.mismatch_dimensions) > 0,
                "mismatch_dimensions": eroi.mismatch_dimensions,
            },
            "raw_text": raw_text,
        }
        return entry

    # ── Dedup helpers ────────────────────────────────────────────────

    def _find_entry_index(self, linkedin_job_id: str, eroi: EROIResult) -> int | None:
        """Find existing entry index in metadata.json by linkedin_job_id
        or by normalized title+company match."""
        try:
            with open(self.metadata_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        entries = data.get("entries", [])

        # Exact LinkedIn job ID match (strongest)
        if linkedin_job_id:
            for i, entry in enumerate(entries):
                stored_li_id = entry.get("linkedin_job_id", "")
                if stored_li_id and stored_li_id == linkedin_job_id:
                    return i

        # Title + company match (fallback)
        new_norm = _normalize(f"{eroi.job_title}|{eroi.company}")
        for i, entry in enumerate(entries):
            stored_norm = _normalize(
                f"{entry.get('title', '')}|{entry.get('company', {}).get('industry', '')}"
            )
            if stored_norm == new_norm:
                return i

        return None

    def append_to_report(self, eroi: EROIResult, raw_text: str = "") -> None:
        block = self._format_entry_md(eroi, raw_text)
        if not self.report_path.exists():
            self.report_path.write_text(block, encoding="utf-8")
            return

        content = self.report_path.read_text(encoding="utf-8")
        summary_marker = "## Souhrnná statistika"
        if summary_marker in content:
            content = content.replace(summary_marker, f"{block}\n\n{summary_marker}", 1)
        else:
            content += f"\n{block}\n"
        self.report_path.write_text(content, encoding="utf-8")

    def _update_summary_table(self, eroi: EROIResult) -> None:
        content = self.report_path.read_text(encoding="utf-8")
        icon = VERDICT_ICON.get(eroi.verdict, "")
        eroi_label = EROI_LABEL.get(eroi.verdict, "")
        fid = self._format_id(int(eroi.job_id))
        new_row = (
            f"| {fid} | {eroi.company} | {eroi.job_title}"
            f" | {eroi.total_score}% | {eroi_label} | {icon} {eroi.verdict} |"
        )

        table_header = "| # | Firma | Role | Fit % | EROI | Verdikt |"
        if table_header in content:
            lines = content.split("\n")
            result_lines = []
            found_table = False
            row_replaced = False
            for line in lines:
                if line.strip().startswith("|---"):
                    found_table = True
                if found_table and line.strip().startswith(f"| {fid} |"):
                    result_lines.append(new_row)
                    row_replaced = True
                    continue
                result_lines.append(line)
            if found_table and not row_replaced:
                result_lines.append(new_row)
            if found_table:
                self.report_path.write_text("\n".join(result_lines), encoding="utf-8")
        else:
            logger.info("Summary table not found, skipping update")

    def _load_metadata(self) -> dict[str, Any]:
        if self.metadata_path.exists():
            with open(self.metadata_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "_meta": {
                "description": "Strojově čitelná agregace požadavků z LinkedIn nabídek",
                "schema_version": "1.1",
                "target_profile": "Ondřej Soušek — Systems Integrator",
                "layers": [
                    "role",
                    "tech_stack",
                    "domain",
                    "formal_requirements",
                    "company",
                    "eroi",
                ],
            },
            "entries": [],
        }

    def upsert_metadata(self, eroi: EROIResult, linkedin_job_id: str = "", raw_text: str = "") -> bool:
        """Insert or update entry in metadata.json.

        Returns True if an existing entry was updated, False if new.
        """
        data = self._load_metadata()
        entry = self._format_entry_json(eroi, linkedin_job_id, raw_text)
        idx = self._find_entry_index(linkedin_job_id, eroi)

        if idx is not None:
            data["entries"][idx] = entry
            updated = True
        else:
            data["entries"].append(entry)
            updated = False

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return updated

    def _upsert_report_block(self, eroi: EROIResult, new_block: str) -> bool:
        """Find existing block in report by ID or title+company and replace it.

        Returns True if replaced, False if not found (caller should append).
        """
        if not self.report_path.exists():
            return False

        content = self.report_path.read_text(encoding="utf-8")
        fid = self._format_id(int(eroi.job_id))

        # Split into sections (each starts with ##)
        sections = re.split(r"^(?=## )", content, flags=re.MULTILINE)

        replaced = False
        new_sections: list[str] = []
        for section in sections:
            if not replaced:
                id_match = re.search(rf"ZÁZNAM #{fid} —", section)
                if id_match:
                    new_sections.append(new_block)
                    replaced = True
                    continue
            new_sections.append(section)

        if replaced:
            self.report_path.write_text("".join(new_sections), encoding="utf-8")

        return replaced

    def write_all(
        self,
        eroi: EROIResult,
        raw_text: str = "",
        linkedin_job_id: str = "",
    ) -> dict[str, Any]:
        # Check if this job already exists (by linkedin_job_id)
        idx = None
        if linkedin_job_id:
            idx = self._find_entry_index(linkedin_job_id, eroi)

        if idx is not None:
            # ── Update existing ──
            data = self._load_metadata()
            existing_id = data["entries"][idx]["id"]
            eroi.job_id = existing_id
            fid = existing_id

            entry = self._format_entry_json(eroi, linkedin_job_id, raw_text)
            data["entries"][idx] = entry
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            new_block = self._format_entry_md(eroi, raw_text)
            replaced = self._upsert_report_block(eroi, new_block)
            if not replaced:
                self.append_to_report(eroi, raw_text)

            updated = True
        else:
            # ── New entry ──
            next_id = self.get_next_id()
            eroi.job_id = str(next_id)
            fid = self._format_id(next_id)

            self.upsert_metadata(eroi, linkedin_job_id, raw_text)
            self.append_to_report(eroi, raw_text)
            updated = False

        try:
            self._update_summary_table(eroi)
        except Exception as e:
            logger.warning("Summary update failed: %s", e)

        if not updated:
            self.commit_changes()

        return {
            "status": "ok",
            "entry_id": fid,
            "updated": updated,
            "report_path": str(self.report_path),
            "metadata_path": str(self.metadata_path),
        }

    def get_raw_text(self, linkedin_job_id: str) -> str:
        """Retrieve cached raw_text from metadata_stacku.json by job ID."""
        try:
            data = self._load_metadata()
            for entry in data.get("entries", []):
                if entry.get("linkedin_job_id") == linkedin_job_id:
                    return entry.get("raw_text", "")
        except Exception:
            pass
        return ""

    def get_existing_ids_with_text(self) -> dict[str, str]:
        """Return {linkedin_job_id: raw_text} for all entries in KB."""
        result: dict[str, str] = {}
        try:
            data = self._load_metadata()
            for entry in data.get("entries", []):
                jid = entry.get("linkedin_job_id", "")
                if jid:
                    result[jid] = entry.get("raw_text", "")
        except Exception:
            pass
        return result

    def commit_changes(self, message: str | None = None) -> None:
        if message is None:
            message = f"[ANALÝZY] add: EROI scoring batch #{date.today().isoformat()}"
        try:
            repo_root = self.linkedin_dir.parents[1]
            subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=repo_root,
                check=True,
                capture_output=True,
            )
            logger.info("Committed KB changes: %s", message)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else ""
            if "nothing to commit" in stderr:
                logger.info("Nothing to commit in KB repo")
            else:
                logger.warning("Git commit failed: %s", stderr)
