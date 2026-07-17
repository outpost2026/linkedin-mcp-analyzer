"""Network layer — RequestInterceptor middleware pipeline.

Pattern: obscura async_trait RequestInterceptor (crates/obscura-net/src/interceptor.rs)
"""

from linkedin_mcp_custom.net.interceptor import (
    InterceptAction,
    InterceptorChain,
    NavigationInfo,
    NavigationInterceptor,
)

__all__ = [
    "InterceptAction",
    "InterceptorChain",
    "NavigationInfo",
    "NavigationInterceptor",
]
