"""Synthetic report generator — deterministic (L1) from metadata_stacku.json.

Computes verdict distribution, skill frequency, SNR, mismatch stats,
cluster assignments, top entries, and writes:
  - synteticky_report_{date}.md   (human-readable)
  - synthetic_report_{date}.json  (machine-readable)

Usage (standalone):
    from linkedin_mcp_custom.analysis.report_generator import SyntheticReportGenerator
    gen = SyntheticReportGenerator()
    md_path, json_path = gen.generate()
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VERDICT_ICON = {
    "SLEDOVAT": "🟢",
    "MEDIUM": "🟡",
    "HRANICNI": "🟡",
    "NESLEDOVAT": "🔴",
}

VERDICT_ORDER = ["SLEDOVAT", "MEDIUM", "HRANICNI", "NESLEDOVAT"]


def _default_kb_path() -> Path:
    return (
        Path.home()
        / "Documents"
        / "Repozitar_Dev"
        / "_github"
        / "B2B-Knowledge-Base"
        / "02_ANALÝZY"
        / "00_linkedin"
    )


class SyntheticReportGenerator:
    """Deterministic synthetic report generator from metadata_stacku.json."""

    def __init__(self, linkedin_dir: str | Path | None = None):
        self.linkedin_dir = Path(linkedin_dir) if linkedin_dir else _default_kb_path()
        self.metadata_path = self.linkedin_dir / "metadata_stacku.json"

    # ── Load ─────────────────────────────────────────────────────────

    def load_metadata(self) -> list[dict[str, Any]]:
        """Load entries from metadata_stacku.json."""
        if not self.metadata_path.exists():
            logger.warning("Metadata not found at %s", self.metadata_path)
            return []
        with open(self.metadata_path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", [])
        logger.info("Loaded %d entries from %s", len(entries), self.metadata_path)
        return entries

    # ── Statistics ───────────────────────────────────────────────────

    @staticmethod
    def _compute_verdict_dist(entries: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in entries:
            v = ((e.get("eroi", {}) or {}).get("verdict")) or "UNKNOWN"
            counts[v] = counts.get(v, 0) + 1
        return counts

    @staticmethod
    def _compute_scores(entries: list[dict]) -> list[float]:
        scores: list[float] = []
        for e in entries:
            s = (e.get("eroi", {}) or {}).get("fit_score_pct")
            if s is not None:
                scores.append(float(s))
        return scores

    @staticmethod
    def _compute_skill_frequency(
        entries: list[dict],
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for e in entries:
            tech = (e.get("tech_stack", {}) or {}).get("overlap_with_author", {}) or {}
            for match_type in ("direct_match", "partial_match", "no_match"):
                for skill in tech.get(match_type, []):
                    counter[skill] += 1
        return dict(counter.most_common())

    @staticmethod
    def _compute_snr(
        entries: list[dict],
    ) -> dict[str, dict[str, int | float]]:
        """Signal-to-Noise Ratio: (sledovat count) / (total count) per skill."""
        total: Counter[str] = Counter()
        sledovat: Counter[str] = Counter()
        for e in entries:
            verdict = ((e.get("eroi", {}) or {}).get("verdict")) or ""
            tech = (e.get("tech_stack", {}) or {}).get("overlap_with_author", {}) or {}
            for match_type in ("direct_match", "partial_match", "no_match"):
                for skill in tech.get(match_type, []):
                    total[skill] += 1
                    if verdict == "SLEDOVAT":
                        sledovat[skill] += 1
        result: dict[str, dict[str, int | float]] = {}
        for skill in total:
            result[skill] = {
                "count": total[skill],
                "sledovat_count": sledovat[skill],
                "snr_pct": round(sledovat[skill] / total[skill] * 100, 1),
            }
        return dict(sorted(result.items(), key=lambda x: x[1]["snr_pct"], reverse=True))

    @staticmethod
    def _compute_mismatch_freq(
        entries: list[dict],
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for e in entries:
            dims = (e.get("eroi", {}) or {}).get("mismatch_dimensions") or []
            for d in dims:
                counter[d] += 1
        return dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _detect_cluster(entry: dict) -> str:
        title = (entry.get("title") or "").lower()
        eroi_data = entry.get("eroi", {}) or {}
        domain_score = 0.0
        # approximate domain score from metadata isn't directly stored,
        # so we infer from verdict + mismatch_dimensions
        mismatch = eroi_data.get("mismatch_dimensions") or []
        verdict = eroi_data.get("verdict", "")
        tech = (entry.get("tech_stack", {}) or {}).get("overlap_with_author", {}) or {}
        direct = set(tech.get("direct_match", []))

        domain_mismatch = "domain" in mismatch
        high_score = (eroi_data.get("fit_score_pct") or 0) >= 65

        has_iot_cam_cnc = bool(direct & {"IoT", "CAM", "CNC", "PLC", "industrial"})

        if has_iot_cam_cnc or (high_score and not domain_mismatch):
            return "industrial_automation_core"

        ai_pattern = re.search(
            r"\b(ai|ml\b|llm|machine learning|data science|artificial intelligence)\b",
            title,
        )
        if ai_pattern:
            return "ai_ml_hype"

        enterprise_pattern = re.search(
            r"\b(architect|solution architect|devops|full.?stack|backend|frontend|saas)\b",
            title,
        )
        if enterprise_pattern:
            return "enterprise_it"

        data_pattern = re.search(
            r"\b(data engineer|data pipeline|etl|data integration)\b",
            title,
        )
        if data_pattern:
            return "data_engineering"

        embedded_pattern = re.search(
            r"\b(embedded|firmware|hardware|test engineer|rd|research)\b",
            title,
        )
        if embedded_pattern:
            return "embedded_manufacturing"

        return "other"

    @staticmethod
    def _compute_clusters(
        entries: list[dict],
    ) -> dict[str, dict[str, Any]]:
        clusters: dict[str, list[dict]] = {}
        for e in entries:
            c = SyntheticReportGenerator._detect_cluster(e)
            clusters.setdefault(c, []).append(e)

        result: dict[str, dict[str, Any]] = {}
        for name, members in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
            scores = [(m.get("eroi", {}) or {}).get("fit_score_pct") or 0 for m in members]
            result[name] = {
                "count": len(members),
                "mean_score": round(statistics.mean(scores), 1) if scores else 0,
                "entry_ids": [m.get("id", "") for m in members],
            }
        return result

    @staticmethod
    def _compute_skill_gaps(
        entries: list[dict],
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for e in entries:
            tech = (e.get("tech_stack", {}) or {}).get("overlap_with_author", {}) or {}
            for skill in tech.get("no_match", []):
                counter[skill] += 1
        return dict(counter.most_common())

    @staticmethod
    def _compute_direct_matches(
        entries: list[dict],
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for e in entries:
            tech = (e.get("tech_stack", {}) or {}).get("overlap_with_author", {}) or {}
            for skill in tech.get("direct_match", []):
                counter[skill] += 1
        return dict(counter.most_common())

    @staticmethod
    def _top_entries(
        entries: list[dict],
        n: int = 10,
    ) -> list[dict]:
        scored = [
            {
                "id": e.get("id", ""),
                "title": e.get("title", ""),
                "company": ((e.get("company", {}) or {}).get("industry")) or "",
                "score": (e.get("eroi", {}) or {}).get("fit_score_pct") or 0,
                "verdict": (e.get("eroi", {}) or {}).get("verdict", ""),
            }
            for e in entries
            if (e.get("eroi", {}) or {}).get("fit_score_pct") is not None
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n]

    # ── Generate reports ─────────────────────────────────────────────

    def _compute_stats(
        self,
        entries: list[dict],
    ) -> dict[str, Any]:
        scores = self._compute_scores(entries)
        verdict_dist = self._compute_verdict_dist(entries)
        total = len(entries)
        sledovat_count = verdict_dist.get("SLEDOVAT", 0)
        precision = round(sledovat_count / total * 100, 1) if total else 0.0
        return {
            "total": total,
            "verdict_distribution": verdict_dist,
            "precision_pct": precision,
            "mean_score": round(statistics.mean(scores), 1) if scores else 0.0,
            "median_score": round(statistics.median(scores), 1) if scores else 0.0,
            "scores": scores,
        }

    def generate(
        self,
        entries: list[dict] | None = None,
    ) -> tuple[Path, Path]:
        """Main entry point: load metadata, compute stats, write reports.

        Args:
            entries: Optional pre-loaded entries (otherwise loads from file).

        Returns:
            Tuple of (md_path, json_path).
        """
        if entries is None:
            entries = self.load_metadata()
        if not entries:
            logger.warning("No entries to generate report from")
            md_path = self.linkedin_dir / f"synteticky_report_{date.today().isoformat()}.md"
            json_path = self.linkedin_dir / f"synthetic_report_{date.today().isoformat()}.json"
            for p in (md_path, json_path):
                p.write_text("{}" if p.suffix == ".json" else "# No data\n", encoding="utf-8")
            return md_path, json_path

        stats = self._compute_stats(entries)
        skill_freq = self._compute_skill_frequency(entries)
        snr = self._compute_snr(entries)
        mismatch_freq = self._compute_mismatch_freq(entries)
        clusters = self._compute_clusters(entries)
        top = self._top_entries(entries)
        skill_gaps = self._compute_skill_gaps(entries)
        direct_matches = self._compute_direct_matches(entries)

        md_path = self.linkedin_dir / f"synteticky_report_{date.today().isoformat()}.md"
        json_path = self.linkedin_dir / f"synthetic_report_{date.today().isoformat()}.json"

        self._write_md_report(
            md_path,
            entries,
            stats,
            skill_freq,
            snr,
            mismatch_freq,
            clusters,
            top,
            skill_gaps,
            direct_matches,
        )
        self._write_json_report(
            json_path,
            entries,
            stats,
            skill_freq,
            snr,
            mismatch_freq,
            clusters,
            top,
            skill_gaps,
            direct_matches,
        )

        logger.info("Reports written:\n  MD:  %s\n  JSON: %s", md_path, json_path)
        return md_path, json_path

    def _write_md_report(
        self,
        path: Path,
        entries: list[dict],
        stats: dict[str, Any],
        skill_freq: dict[str, int],
        snr: dict[str, dict[str, int | float]],
        mismatch_freq: dict[str, int],
        clusters: dict[str, dict[str, Any]],
        top_entries: list[dict],
        skill_gaps: dict[str, int],
        direct_matches: dict[str, int],
    ) -> None:
        today = date.today().isoformat()
        lines: list[str] = []
        lines.append(f"# Syntetický report — Analýza LinkedIn tržních signálů (v4)")
        lines.append("")
        lines.append(
            f"**Autor profilu:** Ondřej Soušek — Systems Integrator (industrial automation, formalizace, reverse engineering, CAM/CNC)"
        )
        lines.append(f"**Zpracováno:** {today} (automatický generátor)")
        lines.append(f"**Vzorek:** {stats['total']} nabídek, Praha/CZ trh")
        lines.append(f"**Pipeline:** deterministic L1 report generator (Phase 7)")
        lines.append("")

        # ── 1. Overview ──
        lines.append("## 1. Přehledová statistika")
        lines.append("")
        lines.append("| Metrika | Hodnota |")
        lines.append("|---------|---------|")
        lines.append(f"| Celkem nabídek | {stats['total']} |")
        for v in VERDICT_ORDER:
            count = stats["verdict_distribution"].get(v, 0)
            icon = VERDICT_ICON.get(v, "")
            lines.append(
                f"| {icon} {v} (≥{65 if v == 'SLEDOVAT' else 50 if v == 'MEDIUM' else 40 if v == 'HRANICNI' else 0}%) | {count} |"
            )
        lines.append(f"| Precision (SLEDOVAT / celkem) | {stats['precision_pct']}% |")
        lines.append(f"| Mean score | {stats['mean_score']}% |")
        lines.append(f"| Median score | {stats['median_score']}% |")
        lines.append("")

        # ── 2. Skill frequency ──
        core_freq = {k: v for k, v in skill_freq.items() if v >= 4}
        sec_freq = {k: v for k, v in skill_freq.items() if 2 <= v <= 3}
        edge_freq = {k: v for k, v in skill_freq.items() if v == 1}

        lines.append("## 2. Tech Stack Frequency Matrix")
        lines.append("")
        if core_freq:
            max_bar = max(core_freq.values()) if core_freq else 1
            lines.append("### CORE (≥4 výskyty)")
            lines.append("")
            for skill, count in core_freq.items():
                bar_len = int(count / max_bar * 60)
                bar = "█" * bar_len
                lines.append(f"  {skill:30s} {bar} {count}×")
            lines.append("")
        if sec_freq:
            lines.append("### SECONDARY (2-3 výskyty)")
            lines.append("")
            for skill, count in sec_freq.items():
                lines.append(f"  {skill:30s} {'█' * count} {count}×")
            lines.append("")
        if edge_freq:
            lines.append("### EDGE (1 výskyt)")
            for skill in edge_freq:
                lines.append(f"  {skill}")
            lines.append("")

        # ── 3. SNR ──
        lines.append("## 3. Signal-to-Noise Ratio (technologie s ≥2 výskyty)")
        lines.append("")
        lines.append("| Technologie | Výskyt | Z toho SLEDOVAT | SNR |")
        lines.append("| --- | --- | --- | --- |")
        for skill, data in snr.items():
            if data["count"] >= 2:
                lines.append(
                    f"| {skill} | {data['count']} | {data['sledovat_count']} | {data['snr_pct']}% |"
                )
        lines.append("")

        # ── 4. Mismatch ──
        lines.append("## 4. Mismatch dimenze (kritické gapy)")
        lines.append("")
        lines.append("| Dimenze | Počet výskytů | Podíl |")
        lines.append("| --- | --- | --- |")
        for dim, count in mismatch_freq.items():
            pct = round(count / stats["total"] * 100, 1) if stats["total"] else 0
            lines.append(f"| {dim} | {count} | {pct}% |")
        lines.append("")

        # ── 5. Clusters ──
        lines.append("## 5. Klastry a patterny")
        lines.append("")
        for cname, cdata in clusters.items():
            label = cname.replace("_", " ").title()
            lines.append(f"### {label}")
            lines.append(f"- **Počet nabídek:** {cdata['count']}")
            lines.append(f"- **Průměrné EROI:** {cdata['mean_score']}%")
            lines.append(f"- **IDs:** {', '.join(cdata['entry_ids'])}")
            lines.append("")

        # ── 6. Skill gaps ──
        lines.append("## 6. Skill Gaps & CV Optimization")
        lines.append("")
        lines.append("### Nejčastější no-match (gapy)")
        lines.append("")
        for skill, count in list(skill_gaps.items())[:10]:
            lines.append(f"- **{skill}**: {count}×")
        lines.append("")
        lines.append("### Nejčastější direct match (autorovy silné stránky)")
        lines.append("")
        for skill, count in list(direct_matches.items())[:10]:
            lines.append(f"- **{skill}**: {count}×")
        lines.append("")

        # ── 7. Top 10 ──
        lines.append("## 7. Top 10 nabídek (dle EROI skóre)")
        lines.append("")
        lines.append("| # | ID | Titul | Firma | Skóre | Verdikt |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for rank, entry in enumerate(top_entries, 1):
            icon = VERDICT_ICON.get(entry["verdict"], "")
            lines.append(
                f"| {rank} | {entry['id']} | {entry['title']} | {entry['company']}"
                f" | {entry['score']}% | {icon} {entry['verdict']} |"
            )
        lines.append("")

        # ── 8. Conclusion ──
        lines.append("## 8. Závěr a doporučení")
        lines.append("")
        sledovat_count = stats["verdict_distribution"].get("SLEDOVAT", 0)
        medium_count = stats["verdict_distribution"].get("MEDIUM", 0)
        hranicni_count = stats["verdict_distribution"].get("HRANICNI", 0)
        nesledovat_count = stats["verdict_distribution"].get("NESLEDOVAT", 0)
        lines.append(
            f"Ze {stats['total']} analyzovaných nabídek: "
            f"**{sledovat_count} SLEDOVAT** ({stats['precision_pct']}% precision), "
            f"**{medium_count} MEDIUM**, **{hranicni_count} HRANIČNÍ**, "
            f"**{nesledovat_count} NESLEDOVAT**."
        )
        lines.append("")
        lines.append("### Doporučené akce")
        lines.append("")
        for e in top_entries[:5]:
            icon = VERDICT_ICON.get(e["verdict"], "")
            lines.append(
                f"- {icon} Aplikovat na #{e['id']} {e['company']} ({e['title']}, {e['score']}%)"
            )
        lines.append("")

        # ── 9. Pipeline metadata ──
        lines.append("## 9. Pipeline Metadata")
        lines.append("")
        lines.append(f"| Parametr | Hodnota |")
        lines.append(f"| --- | --- |")
        lines.append(f"| Generátor | deterministic L1 report generator |")
        lines.append(f"| Datum | {today} |")
        lines.append(f"| Vstup | metadata_stacku.json ({stats['total']} entries) |")
        lines.append(
            f"| Metodika | EROI scoring (6 dimenzí) + frequency analysis + SNR + cluster detection |"
        )
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            f"*Report generated automatically by SyntheticReportGenerator (Phase 7) on {today}*"
        )
        lines.append(f"*Vstupní data: metadata_stacku.json ({stats['total']} entries)*")
        lines.append(
            f"*Metodika: EROI scoring (6 dimenzí) + frequency analysis + SNR computation + rule-based clustering*"
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_json_report(
        self,
        path: Path,
        entries: list[dict],
        stats: dict[str, Any],
        skill_freq: dict[str, int],
        snr: dict[str, dict[str, int | float]],
        mismatch_freq: dict[str, int],
        clusters: dict[str, dict[str, Any]],
        top_entries: list[dict],
        skill_gaps: dict[str, int],
        direct_matches: dict[str, int],
    ) -> None:
        today = date.today().isoformat()
        report: dict[str, Any] = {
            "_meta": {
                "generated": today,
                "source": "metadata_stacku.json",
                "entries_count": stats["total"],
                "pipeline": "deterministic L1 report generator (Phase 7)",
                "generator": "SyntheticReportGenerator",
            },
            "overview": {
                "total": stats["total"],
                "precision_pct": stats["precision_pct"],
                "mean_score": stats["mean_score"],
                "median_score": stats["median_score"],
                "verdict_distribution": stats["verdict_distribution"],
            },
            "skill_frequency": skill_freq,
            "signal_to_noise": snr,
            "mismatch_frequency": mismatch_freq,
            "clusters": clusters,
            "top_entries": top_entries,
            "skill_gaps": skill_gaps,
            "direct_matches": direct_matches,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
