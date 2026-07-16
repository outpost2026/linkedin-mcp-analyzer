"""Unit tests for browser.py using AsyncMock."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from linkedin_mcp_custom.core.browser import (
    _BLOCKED_DOMAINS,
    _BLOCKED_RESOURCE_TYPES,
    _PENDING_NAV_TASKS,
    MAX_PAGE_POOL_SIZE,
    _drain_pending_navs,
    _ensure_profile_dir,
    _page_pool,
    _track_nav_task,
    close_browser,
    close_session,
    create_page,
    get_page,
)


def test_blocked_resource_types():
    assert "image" in _BLOCKED_RESOURCE_TYPES
    assert "font" in _BLOCKED_RESOURCE_TYPES
    assert "media" in _BLOCKED_RESOURCE_TYPES
    assert len(_BLOCKED_RESOURCE_TYPES) == 3


def test_blocked_domains_pattern():
    assert _BLOCKED_DOMAINS.search("https://www.google-analytics.com/collect")
    assert _BLOCKED_DOMAINS.search("https://www.facebook.com/tr")
    assert _BLOCKED_DOMAINS.search("https://www.doubleclick.net/ads")
    assert not _BLOCKED_DOMAINS.search("https://www.linkedin.com/feed/")


def test_max_page_pool_size():
    assert MAX_PAGE_POOL_SIZE == 3


@pytest.mark.asyncio
async def test_drain_no_tasks():
    _PENDING_NAV_TASKS.clear()
    await _drain_pending_navs(timeout=0.1)
    assert len(_PENDING_NAV_TASKS) == 0


@pytest.mark.asyncio
async def test_track_nav_task():
    _PENDING_NAV_TASKS.clear()

    async def dummy():
        pass

    task = asyncio.ensure_future(dummy())
    _track_nav_task(task)
    assert len(_PENDING_NAV_TASKS) == 1
    await task


@pytest.mark.asyncio
async def test_track_nav_task_none():
    _PENDING_NAV_TASKS.clear()
    _track_nav_task(None)
    assert len(_PENDING_NAV_TASKS) == 0


@pytest.mark.asyncio
async def test_close_browser_cleanup():
    _page_pool.clear()
    _PENDING_NAV_TASKS.clear()

    with patch("linkedin_mcp_custom.core.browser._context", None):
        with patch("linkedin_mcp_custom.core.browser._page", None):
            with patch("linkedin_mcp_custom.core.browser._playwright", None):
                await close_browser()


@pytest.mark.asyncio
async def test_close_session_alias():
    _page_pool.clear()
    _PENDING_NAV_TASKS.clear()

    with patch("linkedin_mcp_custom.core.browser._context", None):
        with patch("linkedin_mcp_custom.core.browser._page", None):
            with patch("linkedin_mcp_custom.core.browser._playwright", None):
                await close_session()


@pytest.mark.asyncio
async def test_create_page_calls_get_browser_context():
    mock_ctx = AsyncMock()
    mock_ctx.new_page = AsyncMock(return_value=AsyncMock())
    mock_get_ctx = AsyncMock(return_value=mock_ctx)

    _page_pool.clear()

    with patch("linkedin_mcp_custom.core.browser._context", mock_ctx):
        with patch(
            "linkedin_mcp_custom.core.browser.get_browser_context",
            new=mock_get_ctx,
        ):
            result = await create_page()
            assert result is not None
            mock_get_ctx.assert_awaited_once()


def test_ensure_profile_dir():
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        result = _ensure_profile_dir()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result is not None


@pytest.mark.asyncio
async def test_get_page_returns_existing():
    mock_page = MagicMock()
    mock_page.is_closed.return_value = False

    with patch("linkedin_mcp_custom.core.browser._page", mock_page):
        with patch("linkedin_mcp_custom.core.browser._context", MagicMock()):
            result = await get_page()
            assert result == mock_page
