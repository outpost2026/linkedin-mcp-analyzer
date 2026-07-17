"""RequestInterceptor pipeline — middleware chain for page navigation.

Pattern: obscura async_trait RequestInterceptor + InterceptAction enum
(crates/obscura-net/src/interceptor.rs)

Each interceptor implements ``before_navigate`` and/or ``after_navigate``
hooks. The chain runs all interceptors in registration order, and any
interceptor can block navigation (return BLOCK).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import auto, StrEnum
from typing import Any

from patchright.async_api import Page

logger = logging.getLogger(__name__)


class InterceptAction(StrEnum):
    """Action an interceptor can take after inspecting a navigation."""

    CONTINUE = auto()  # Proceed with the navigation.
    BLOCK = auto()     # Abort the navigation (caller should handle).


@dataclass
class NavigationInfo:
    """Context captured around a single page navigation/extraction."""

    url: str
    section_name: str = "content"
    status_code: int | None = None
    duration_ms: float = 0.0
    extracted_text_len: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class NavigationInterceptor(ABC):
    """Abstract interceptor with before/after hooks.

    Subclasses implement one or both hooks. The chain calls
    ``before_navigate`` before navigation and
    ``after_navigate`` after extraction completes.
    """

    @abstractmethod
    async def before_navigate(self, page: Page, info: NavigationInfo) -> InterceptAction:
        """Called before every page navigation.

        Return CONTINUE to proceed, BLOCK to abort.
        """

    @abstractmethod
    async def after_navigate(self, page: Page, info: NavigationInfo) -> None:
        """Called after extraction completes (success or error).

        Use for audit logging, metrics, cleanup.
        """


class InterceptorChain:
    """Chain of NavigationInterceptor instances.

    Usage::

        chain = InterceptorChain([
            AuthInterceptor(),
            RateLimitInterceptor(),
            AuditInterceptor(),
        ])
        info = await chain.run(page, "https://...", "job_posting")
    """

    def __init__(self, interceptors: list[NavigationInterceptor] | None = None) -> None:
        self._interceptors: list[NavigationInterceptor] = interceptors or []

    def add(self, interceptor: NavigationInterceptor) -> None:
        self._interceptors.append(interceptor)

    async def run(
        self,
        page: Page,
        url: str,
        section_name: str = "content",
    ) -> NavigationInfo:
        """Run the full interceptor chain around a navigation.

        Args:
            page: The Patchright page to navigate.
            url: Target URL.
            section_name: Label for this extraction.

        Returns:
            NavigationInfo with timing, status, and metadata populated
            by all interceptors in the chain.
        """
        info = NavigationInfo(url=url, section_name=section_name)
        start = time.monotonic()

        try:
            for interceptor in self._interceptors:
                action = await interceptor.before_navigate(page, info)
                if action == InterceptAction.BLOCK:
                    info.error = f"Blocked by {type(interceptor).__name__}"
                    logger.info("Navigation blocked by %s", type(interceptor).__name__)
                    return info
        except Exception as exc:
            info.error = f"Interceptor before_navigate failed: {exc}"
            logger.warning(info.error)
            return info

        info.duration_ms = (time.monotonic() - start) * 1000

        try:
            for interceptor in self._interceptors:
                await interceptor.after_navigate(page, info)
        except Exception as exc:
            logger.warning("Interceptor after_navigate failed: %s", exc)

        return info


# ── Built-in interceptor implementations ──────────────────────────────


class AuthInterceptor(NavigationInterceptor):
    """Ensures LinkedIn authentication is valid before navigation.

    Delegates to ``ensure_authenticated`` from core/auth.
    """

    def __init__(self) -> None:
        self._last_check: float = 0.0
        self._check_interval: float = 60.0  # seconds between auth checks

    async def before_navigate(self, page: Page, info: NavigationInfo) -> InterceptAction:
        from linkedin_mcp_custom.core.auth import ensure_authenticated

        now = time.time()
        if now - self._last_check < self._check_interval:
            return InterceptAction.CONTINUE

        try:
            await ensure_authenticated(page)
            self._last_check = now
            return InterceptAction.CONTINUE
        except Exception:
            info.error = "Authentication failed"
            return InterceptAction.BLOCK

    async def after_navigate(self, page: Page, info: NavigationInfo) -> None:
        return  # auth is pre-flight only


class AuditInterceptor(NavigationInterceptor):
    """Logs every navigation to the audit trail.

    Records URL, section, duration, text length, and error status
    into the logger for post-mortem analysis.
    """

    def __init__(self) -> None:
        self._call_count: int = 0

    async def before_navigate(self, page: Page, info: NavigationInfo) -> InterceptAction:
        return InterceptAction.CONTINUE

    async def after_navigate(self, page: Page, info: NavigationInfo) -> None:
        self._call_count += 1
        if info.error:
            logger.warning(
                "[AUDIT #%d] %s %s — FAIL: %s (%.0f ms)",
                self._call_count,
                info.section_name,
                info.url,
                info.error,
                info.duration_ms,
            )
        else:
            logger.info(
                "[AUDIT #%d] %s %s — OK (%d chars, %.0f ms)",
                self._call_count,
                info.section_name,
                info.url,
                info.extracted_text_len,
                info.duration_ms,
            )


class RateLimitInterceptor(NavigationInterceptor):
    """Detects rate-limiting after navigation and blocks follow-ups.

    Checks the page body for rate-limit signals after extraction.
    If detected, marks the info as errored so the caller can back off.
    """

    def __init__(self, cooldown_seconds: float = 30.0) -> None:
        self._cooldown_until: float = 0.0
        self._cooldown_seconds = cooldown_seconds

    async def before_navigate(self, page: Page, info: NavigationInfo) -> InterceptAction:
        if time.time() < self._cooldown_until:
            remaining = self._cooldown_until - time.time()
            info.error = f"Rate-limit cooldown active ({remaining:.0f}s remaining)"
            return InterceptAction.BLOCK
        return InterceptAction.CONTINUE

    async def after_navigate(self, page: Page, info: NavigationInfo) -> None:
        if info.error:
            return  # navigation already failed
        try:
            from linkedin_mcp_custom.scraping.utils import is_rate_limited

            body = await page.text_content("body")
            if body and is_rate_limited(body):
                self._cooldown_until = time.time() + self._cooldown_seconds
                info.error = "Rate-limited by LinkedIn"
                logger.warning(
                    "Rate-limited at %s — cooling down for %.0fs",
                    info.url,
                    self._cooldown_seconds,
                )
        except Exception:
            pass
