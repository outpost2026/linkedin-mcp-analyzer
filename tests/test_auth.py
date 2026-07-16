"""Unit tests for auth.py using AsyncMock."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from linkedin_mcp_custom.core import auth as auth_module
from linkedin_mcp_custom.core.auth import (
    SESSION_CHECK_INTERVAL,
    check_cached_auth,
    detect_rate_limit,
    ensure_authenticated,
    get_session_age,
    is_logged_in,
    session_needs_refresh,
)
from linkedin_mcp_custom.core.exceptions import AuthenticationError, RateLimitError


def setup_module():
    auth_module._last_auth_check = None
    auth_module._last_auth_ok = None


def test_check_cached_auth_never_checked():
    assert check_cached_auth() is False


def test_check_cached_auth_ok():
    with patch("linkedin_mcp_custom.core.auth._last_auth_check", time.time()):
        with patch("linkedin_mcp_custom.core.auth._last_auth_ok", True):
            assert check_cached_auth() is True


def test_check_cached_auth_expired():
    old_time = time.time() - SESSION_CHECK_INTERVAL - 10
    with patch("linkedin_mcp_custom.core.auth._last_auth_check", old_time):
        with patch("linkedin_mcp_custom.core.auth._last_auth_ok", True):
            assert check_cached_auth() is False


def test_get_session_age_never():
    with patch("linkedin_mcp_custom.core.auth._last_auth_check", None):
        with patch("linkedin_mcp_custom.core.auth._last_auth_ok", None):
            assert get_session_age() is None


def test_session_needs_refresh_never():
    with patch("linkedin_mcp_custom.core.auth._last_auth_check", None):
        with patch("linkedin_mcp_custom.core.auth._last_auth_ok", None):
            assert session_needs_refresh() is True


@pytest.mark.asyncio
async def test_is_logged_in_on_feed():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/feed/"

    result = await is_logged_in(mock_page)
    assert result is True


@pytest.mark.asyncio
async def test_is_logged_in_checkpoint():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/checkpoint/"

    result = await is_logged_in(mock_page)
    assert result is False


@pytest.mark.asyncio
async def test_is_logged_in_login_page():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/login"

    result = await is_logged_in(mock_page)
    assert result is False


@pytest.mark.asyncio
async def test_detect_rate_limit_negative():
    mock_page = AsyncMock()
    mock_page.text_content = AsyncMock(return_value="Welcome to LinkedIn Feed")

    result = await detect_rate_limit(mock_page)
    assert result is False


@pytest.mark.asyncio
async def test_detect_rate_limit_positive():
    mock_page = AsyncMock()
    mock_page.text_content = AsyncMock(return_value="Too many requests. Please try again later.")

    result = await detect_rate_limit(mock_page)
    assert result is True


@pytest.mark.asyncio
async def test_ensure_authenticated_cached():
    now = time.time()
    with patch("linkedin_mcp_custom.core.auth._last_auth_check", now):
        with patch("linkedin_mcp_custom.core.auth._last_auth_ok", True):
            mock_page = AsyncMock()
            await ensure_authenticated(mock_page, force_check=False)
            mock_page.goto.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_authenticated_checkpoint_url():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/checkpoint/"
    mock_page.text_content = AsyncMock(return_value="checkpoint body")

    with patch("linkedin_mcp_custom.core.auth._last_auth_check", None):
        with pytest.raises(AuthenticationError) as exc:
            await ensure_authenticated(mock_page, force_check=True)
        assert "checkpoint" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_ensure_authenticated_rate_limit():
    mock_page = AsyncMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    mock_page.text_content = AsyncMock(return_value="Too many requests")

    with patch("linkedin_mcp_custom.core.auth._last_auth_check", None):
        with pytest.raises(RateLimitError):
            await ensure_authenticated(mock_page, force_check=True)
