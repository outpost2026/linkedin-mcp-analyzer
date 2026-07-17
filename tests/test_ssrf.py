"""Tests for SSRF guard — validate_url and decorator."""

from __future__ import annotations

import pytest

from linkedin_mcp_custom.util.ssrf import SSRFError, validate_url


class TestValidateUrl:
    """validate_url should block private IPs and accept public URLs."""

    def test_public_url_passes(self) -> None:
        assert validate_url("https://www.google.com") == "https://www.google.com"
        assert validate_url("http://example.com/path?q=1") == "http://example.com/path?q=1"

    def test_https_required(self) -> None:
        with pytest.raises(SSRFError, match="Scheme 'ftp' not allowed"):
            validate_url("ftp://files.example.com")
        with pytest.raises(SSRFError, match="not allowed"):
            validate_url("file:///etc/passwd")
        with pytest.raises(SSRFError, match="not allowed"):
            validate_url("data:text/plain,hello")

    def test_loopback_blocked(self) -> None:
        for bad in ("http://127.0.0.1", "http://127.0.0.1:8080", "http://0.0.0.1"):
            with pytest.raises(SSRFError, match="not allowed"):
                validate_url(bad)

    def test_private_ipv4_blocked(self) -> None:
        for bad in ("http://10.0.0.5", "http://172.16.0.1", "http://192.168.1.1"):
            with pytest.raises(SSRFError, match="not allowed"):
                validate_url(bad)

    def test_link_local_blocked(self) -> None:
        with pytest.raises(SSRFError, match="not allowed"):
            validate_url("http://169.254.1.1")

    def test_ipv6_loopback_blocked(self) -> None:
        with pytest.raises(SSRFError, match="not allowed"):
            validate_url("http://[::1]:8080/path")

    def test_dns_failure_raises(self) -> None:
        with pytest.raises(SSRFError, match="DNS resolution failed"):
            validate_url("https://this-domain-does-not-exist-12345.com")

    def test_allow_private_override(self) -> None:
        assert validate_url("http://127.0.0.1", allow_private=True) == "http://127.0.0.1"

    def test_localhost_hostname(self) -> None:
        with pytest.raises(SSRFError, match="not allowed|Private"):
            validate_url("http://localhost")
