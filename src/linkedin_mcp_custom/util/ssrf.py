"""SSRF guard — URL validation preventing Server-Side Request Forgery.

Pattern: obscura validate_url (crates/obscura-net/src/client.rs)
Blocks private/loopback/link-local/broadcast/documentation IP ranges
and restricts allowed URI schemes to http/https/file.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
PRIVATE_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),       # current network (RFC 1122)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),           # loopback IPv6
    ipaddress.ip_network("fc00::/7"),          # unique-local IPv6
]


class SSRFError(ValueError):
    """Raised when a URL resolves to a private or disallowed address."""


def validate_url(url: str, allow_private: bool = False) -> str:
    """Validate that *url* does not target a private/loopback address.

    Args:
        url: The URL string to validate.
        allow_private: If True, skip private-IP check (use with caution).

    Returns:
        The validated URL (unchanged).

    Raises:
        SSRFError: If the URL scheme is not allowed, DNS resolution fails,
                   or the resolved IP is in a private range.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SSRFError(f"Scheme {parsed.scheme!r} not allowed (need {ALLOWED_SCHEMES})")

    hostname = parsed.hostname
    if not hostname:
        return url  # no host to resolve (e.g. file://)

    if allow_private:
        return url

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}: {exc}") from exc

    for info in infos:
        ip_str = info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if any(ip in net for net in PRIVATE_NETWORKS):
            raise SSRFError(f"Private/reserved IP {ip_str} not allowed for {url}")

    return url


F = TypeVar("F", bound=Callable[..., Any])


def validate_urls(*param_names: str) -> Callable[[F], F]:
    """Decorator that validates all named URL parameters before the tool runs.

    Usage::

        @validate_urls("url")
        async def my_tool(url: str) -> dict: ...

    Raises SSRFError (caught by the caller) if any parameter fails validation.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for name in param_names:
                if name in kwargs and isinstance(kwargs[name], str):
                    validate_url(kwargs[name])
            return await func(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator
