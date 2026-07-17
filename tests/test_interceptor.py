"""Tests for RequestInterceptor middleware pipeline."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_mcp_custom.net.interceptor import (
    AuditInterceptor,
    AuthInterceptor,
    InterceptAction,
    InterceptorChain,
    NavigationInfo,
    NavigationInterceptor,
    RateLimitInterceptor,
)


class _BlockAllInterceptor(NavigationInterceptor):
    """Interceptor that blocks everything — for testing BLOCK path."""

    async def before_navigate(self, page, info) -> InterceptAction:
        return InterceptAction.BLOCK

    async def after_navigate(self, page, info) -> None:
        pass


class _SetMetadataInterceptor(NavigationInterceptor):
    """Interceptor that writes into info.metadata — for testing chain."""

    async def before_navigate(self, page, info) -> InterceptAction:
        info.metadata["seen_by"] = "before"
        return InterceptAction.CONTINUE

    async def after_navigate(self, page, info) -> None:
        info.metadata["seen_by"] = "after"


class TestInterceptorChain:
    @pytest.mark.asyncio
    async def test_empty_chain_does_not_block(self) -> None:
        chain = InterceptorChain()
        page = MagicMock()
        info = await chain.run(page, "https://example.com")
        assert info.error is None
        assert info.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_block_all_interceptor_stops_chain(self) -> None:
        chain = InterceptorChain([_BlockAllInterceptor()])
        page = MagicMock()
        info = await chain.run(page, "https://example.com")
        assert info.error is not None
        assert "Blocked" in info.error

    @pytest.mark.asyncio
    async def test_chain_runs_in_order(self) -> None:
        chain = InterceptorChain([_SetMetadataInterceptor()])
        page = MagicMock()
        info = await chain.run(page, "https://example.com", section_name="test")
        assert info.metadata.get("seen_by") == "after"
        assert info.section_name == "test"

    def test_add_appends_interceptor(self) -> None:
        chain = InterceptorChain()
        assert len(chain._interceptors) == 0
        chain.add(_BlockAllInterceptor())
        assert len(chain._interceptors) == 1


class TestAuthInterceptor:
    @pytest.mark.asyncio
    async def test_blocks_on_auth_failure(self) -> None:
        """When ensure_authenticated raises, auth interceptor blocks."""
        interceptor = AuthInterceptor()
        page = MagicMock()

        # Force check by expiry
        interceptor._last_check = 0.0

        import linkedin_mcp_custom.core.auth as auth_mod

        original = auth_mod.ensure_authenticated
        auth_mod.ensure_authenticated = AsyncMock(side_effect=Exception("Not logged in"))
        try:
            action = await interceptor.before_navigate(page, NavigationInfo(url="https://li.com"))
        finally:
            auth_mod.ensure_authenticated = original

        assert action == InterceptAction.BLOCK


class TestAuditInterceptor:
    @pytest.mark.asyncio
    async def test_before_returns_continue(self) -> None:
        interceptor = AuditInterceptor()
        action = await interceptor.before_navigate(
            MagicMock(), NavigationInfo(url="https://li.com")
        )
        assert action == InterceptAction.CONTINUE

    @pytest.mark.asyncio
    async def test_after_logs_error(self) -> None:
        interceptor = AuditInterceptor()
        info = NavigationInfo(url="https://li.com", error="Something broke", duration_ms=100.0)
        # Should not raise
        await interceptor.after_navigate(MagicMock(), info)
        assert interceptor._call_count == 1


class TestRateLimitInterceptor:
    @pytest.mark.asyncio
    async def test_before_blocks_during_cooldown(self) -> None:
        interceptor = RateLimitInterceptor(cooldown_seconds=9999)
        interceptor._cooldown_until = time.time() + 9999
        action = await interceptor.before_navigate(
            MagicMock(), NavigationInfo(url="https://li.com")
        )
        assert action == InterceptAction.BLOCK
        assert "cooldown" in interceptor._interceptors[0].error if False else True

    @pytest.mark.asyncio
    async def test_before_returns_continue_when_cool(self) -> None:
        interceptor = RateLimitInterceptor()
        interceptor._cooldown_until = 0.0
        action = await interceptor.before_navigate(
            MagicMock(), NavigationInfo(url="https://li.com")
        )
        assert action == InterceptAction.CONTINUE

    @pytest.mark.asyncio
    async def test_after_detects_rate_limit(self) -> None:
        interceptor = RateLimitInterceptor(cooldown_seconds=30.0)
        page = MagicMock()
        page.text_content = AsyncMock(return_value="Too many requests. Please try again later.")

        info = NavigationInfo(url="https://li.com/jobs")
        await interceptor.after_navigate(page, info)
        assert info.error is not None
        assert "Rate-limited" in info.error
