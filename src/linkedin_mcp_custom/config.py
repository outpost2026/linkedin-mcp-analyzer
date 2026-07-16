"""Pipeline configuration — YAML-based with env override."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".linkedin-mcp-custom"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class BrowserConfig:
    headless: bool = True
    block_resources: bool = False
    pool_size: int = 1


@dataclass
class ScrapeConfig:
    max_pages: int = 10
    per_job_timeout_ms: int = 30000
    tracker_timeout_ms: int = 30000
    max_nav_retries: int = 0


@dataclass
class PipelineConfig:
    max_concurrent: int = 1
    stagger_delay: float = 1.5
    job_timeout_seconds: int = 120
    headless: bool = True


@dataclass
class EroiThresholds:
    sledovat: float = 65.0  # matches analysis/config.py THRESHOLDS
    medium: float = 50.0
    hranicni: float = 40.0


@dataclass
class AppConfig:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    scrape: ScrapeConfig = field(default_factory=ScrapeConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    thresholds: EroiThresholds = field(default_factory=EroiThresholds)
    config_path: str = ""

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

        b = raw.get("browser", {})
        cfg.browser.headless = b.get("headless", cfg.browser.headless)
        cfg.browser.block_resources = b.get("block_resources", cfg.browser.block_resources)
        cfg.browser.pool_size = b.get("pool_size", cfg.browser.pool_size)

        s = raw.get("scrape", {})
        cfg.scrape.max_pages = s.get("max_pages", cfg.scrape.max_pages)
        cfg.scrape.per_job_timeout_ms = s.get("per_job_timeout_ms", cfg.scrape.per_job_timeout_ms)
        cfg.scrape.tracker_timeout_ms = s.get("tracker_timeout_ms", cfg.scrape.tracker_timeout_ms)
        cfg.scrape.max_nav_retries = s.get("max_nav_retries", cfg.scrape.max_nav_retries)

        p = raw.get("pipeline", {})
        cfg.pipeline.max_concurrent = p.get("max_concurrent", cfg.pipeline.max_concurrent)
        cfg.pipeline.stagger_delay = p.get("stagger_delay", cfg.pipeline.stagger_delay)
        cfg.pipeline.job_timeout_seconds = p.get(
            "job_timeout_seconds", cfg.pipeline.job_timeout_seconds
        )
        cfg.pipeline.headless = p.get("headless", cfg.pipeline.headless)

        t = raw.get("thresholds", {})
        cfg.thresholds.sledovat = t.get("sledovat", cfg.thresholds.sledovat)
        cfg.thresholds.medium = t.get("medium", cfg.thresholds.medium)
        cfg.thresholds.hranicni = t.get("hranicni", cfg.thresholds.hranicni)

        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "browser": {
                "headless": self.browser.headless,
                "block_resources": self.browser.block_resources,
                "pool_size": self.browser.pool_size,
            },
            "scrape": {
                "max_pages": self.scrape.max_pages,
                "per_job_timeout_ms": self.scrape.per_job_timeout_ms,
                "tracker_timeout_ms": self.scrape.tracker_timeout_ms,
                "max_nav_retries": self.scrape.max_nav_retries,
            },
            "pipeline": {
                "max_concurrent": self.pipeline.max_concurrent,
                "stagger_delay": self.pipeline.stagger_delay,
                "job_timeout_seconds": self.pipeline.job_timeout_seconds,
                "headless": self.pipeline.headless,
            },
            "thresholds": {
                "sledovat": self.thresholds.sledovat,
                "medium": self.thresholds.medium,
                "hranicni": self.thresholds.hranicni,
            },
        }

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

    def save_default(self) -> Path:
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(
            yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        return DEFAULT_CONFIG_PATH
