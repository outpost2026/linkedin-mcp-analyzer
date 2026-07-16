"""Pipeline configuration — three-layer YAML structure.

Architektura:
  Layer 1 — SOURCE:     odkud scrapovat (LinkedIn tracker URL, max pages)
  Layer 2 — RUNTIME:    jak engine běží (headless, delay, timeout, fingerprint)
  Layer 3 — ANALYSIS:   N hodnotících profilů s vlastními vahami a prahy EROI

Princip:
  - Jeden YAML = jedna kompletní konfigurace autora
  - Více analysis profilů = více způsobů hodnocení téže nabídky
  - Dev edituje YAML ručně = manuální kalibrace anti-bot + EROI

Příklad:
  user: "ondrej"
  source:
    type: linkedin_saved
    tracker_url: "https://www.linkedin.com/jobs-tracker/"
    max_pages: 10
  runtime:
    headless: true
    delay_range: [3, 7]
    page_timeout_ms: 30000
    session_heartbeat: 30
    fingerprint_mix: true
  analysis:
    default:
      thresholds: { sledovat: 65, medium: 50, hranicni: 40 }
      weights: { domain: 0.35, tech: 0.25, role: 0.20, growth: 0.10, formal: 0.05, location: 0.05 }
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".linkedin-mcp-custom"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"

# ── Global active config (set once, read by analysis modules) ────────
_active_config: AppConfig | None = None
_active_profile: str = "default"


def set_active_config(cfg: AppConfig, profile: str = "default") -> None:
    global _active_config, _active_profile
    _active_config = cfg
    _active_profile = profile


def get_active_config() -> AppConfig | None:
    return _active_config


def get_active_profile() -> str:
    return _active_profile


# ── Layer 1: Source ──────────────────────────────────────────────────
@dataclass
class SourceConfig:
    type: str = "linkedin_saved"
    tracker_url: str = "https://www.linkedin.com/jobs-tracker/"
    max_pages: int = 10


# ── Layer 2: Runtime ─────────────────────────────────────────────────
@dataclass
class RuntimeConfig:
    headless: bool = True
    delay_range: list[float] = field(default_factory=lambda: [3.0, 7.0])
    page_timeout_ms: int = 30000
    session_heartbeat: int = 30
    fingerprint_mix: bool = True
    viewport_pool: list[dict] = field(default_factory=lambda: [
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1920, "height": 1080},
        {"width": 1280, "height": 800},
    ])
    ua_pool: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    ])
    timezone_pool: list[str] = field(default_factory=lambda: [
        "Europe/Prague", "Europe/Berlin", "Europe/London",
    ])
    locale_pool: list[str] = field(default_factory=lambda: [
        "cs-CZ", "en-US", "en-GB",
    ])

    def random_delay(self) -> float:
        return random.uniform(self.delay_range[0], self.delay_range[1])

    def random_viewport(self) -> dict:
        return random.choice(self.viewport_pool)

    def random_ua(self) -> str:
        return random.choice(self.ua_pool)

    def random_timezone(self) -> str:
        return random.choice(self.timezone_pool)

    def random_locale(self) -> str:
        return random.choice(self.locale_pool)


# ── Layer 3: Analysis — jeden profil ─────────────────────────────────
@dataclass
class AnalysisProfile:
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "sledovat": 65.0,
        "medium": 50.0,
        "hranicni": 40.0,
    })
    weights: dict[str, float] = field(default_factory=lambda: {
        "domain": 0.35,
        "tech": 0.25,
        "role": 0.20,
        "growth": 0.10,
        "formal": 0.05,
        "location": 0.05,
    })

    def as_threshold_list(self) -> list[tuple[float, str]]:
        return [
            (self.thresholds.get("sledovat", 65.0), "SLEDOVAT"),
            (self.thresholds.get("medium", 50.0), "MEDIUM"),
            (self.thresholds.get("hranicni", 40.0), "HRANICNI"),
            (0.0, "NESLEDOVAT"),
        ]


# ── AppConfig — kořenový konfigurační objekt ─────────────────────────
@dataclass
class AppConfig:
    user: str = "default"
    source: SourceConfig = field(default_factory=SourceConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    analysis: dict[str, AnalysisProfile] = field(default_factory=lambda: {
        "default": AnalysisProfile(),
    })
    config_path: str = ""

    def get_profile(self, name: str | None = None) -> AnalysisProfile:
        key = name or "default"
        if key not in self.analysis:
            logger.warning("Profile %r not found, falling back to 'default'", key)
            key = "default"
        return self.analysis[key]

    # ── Load methods ─────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls._from_dict(raw, config_path=str(path))

    @classmethod
    def from_defaults(cls) -> AppConfig:
        return cls()

    @classmethod
    def _from_dict(cls, raw: dict, config_path: str = "") -> AppConfig:
        cfg = cls(config_path=config_path)

        cfg.user = raw.get("user", cfg.user)

        # Layer 1: Source
        s = raw.get("source", {})
        cfg.source.type = s.get("type", cfg.source.type)
        cfg.source.tracker_url = s.get("tracker_url", cfg.source.tracker_url)
        cfg.source.max_pages = s.get("max_pages", cfg.source.max_pages)

        # Layer 2: Runtime
        r = raw.get("runtime", {})
        cfg.runtime.headless = r.get("headless", cfg.runtime.headless)
        if "delay_range" in r:
            cfg.runtime.delay_range = [float(v) for v in r["delay_range"]]
        if "page_timeout_ms" in r:
            cfg.runtime.page_timeout_ms = int(r["page_timeout_ms"])
        if "session_heartbeat" in r:
            cfg.runtime.session_heartbeat = int(r["session_heartbeat"])
        if "fingerprint_mix" in r:
            cfg.runtime.fingerprint_mix = bool(r["fingerprint_mix"])

        # Layer 3: Analysis profiles
        raw_profiles = raw.get("analysis", {})
        if raw_profiles:
            cfg.analysis = {}
            for pname, pdata in raw_profiles.items():
                profile = AnalysisProfile()
                if "thresholds" in pdata:
                    profile.thresholds.update(pdata["thresholds"])
                if "weights" in pdata:
                    profile.weights.update(pdata["weights"])
                cfg.analysis[pname] = profile

        return cfg

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        if path:
            return cls.from_yaml(path)
        if DEFAULT_CONFIG_PATH.exists():
            return cls.from_yaml(DEFAULT_CONFIG_PATH)
        env_path = os.environ.get("LINKEDIN_MCP_CONFIG")
        if env_path and Path(env_path).exists():
            return cls.from_yaml(env_path)
        return cls.from_defaults()

    # ── Serialize ────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "user": self.user,
            "source": {
                "type": self.source.type,
                "tracker_url": self.source.tracker_url,
                "max_pages": self.source.max_pages,
            },
            "runtime": {
                "headless": self.runtime.headless,
                "delay_range": self.runtime.delay_range,
                "page_timeout_ms": self.runtime.page_timeout_ms,
                "session_heartbeat": self.runtime.session_heartbeat,
                "fingerprint_mix": self.runtime.fingerprint_mix,
            },
            "analysis": {
                pname: {
                    "thresholds": prof.thresholds,
                    "weights": prof.weights,
                }
                for pname, prof in self.analysis.items()
            },
        }

    def save_default(self) -> Path:
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(
            yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        return DEFAULT_CONFIG_PATH


import logging
logger = logging.getLogger(__name__)
