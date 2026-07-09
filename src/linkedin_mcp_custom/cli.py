"""CLI entry point for linkedin-mcp-custom."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)


async def _login() -> None:
    """Open browser, wait for manual LinkedIn login, save session."""
    from linkedin_mcp_custom.core import (
        AuthenticationError,
        close_browser,
        get_or_create_browser,
        wait_for_manual_login,
    )

    print("Opening browser for LinkedIn login...")
    print("Please log in to LinkedIn in the browser window.")
    print("  If you see a 'Help us confirm it's you' page — complete the")
    print("  verification (CAPTCHA, email code) and you'll be redirected.")
    print("  Use EMAIL + PASSWORD, NOT 'Sign in with Google'.")
    print("(The browser profile will be saved for future use.)")
    print()

    try:
        context = await get_or_create_browser(headless=False)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        await wait_for_manual_login(page, timeout=300)
        print()
        print("[OK] Login successful! Session cookies saved.")
        print("   Profile: ~/.linkedin-mcp-custom/profile/")
    except AuthenticationError as e:
        print(f"[ERROR] Login failed: {e}")
        sys.exit(1)
    finally:
        await close_browser()


async def _status() -> None:
    """Check if LinkedIn session is valid."""
    from linkedin_mcp_custom.core import (
        close_browser,
        get_or_create_browser,
        is_logged_in,
    )

    print("Checking LinkedIn session...")
    try:
        context = await get_or_create_browser(headless=True)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        logged_in = await is_logged_in(page)
        if logged_in:
            print("[OK] Session valid — logged in to LinkedIn")
        else:
            print("[EXPIRED] Session expired — run 'linkedin-mcp --login'")
            sys.exit(1)
    finally:
        await close_browser()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="linkedin-mcp",
        description="LinkedIn saved jobs analysis MCP server with EROI scoring.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for LinkedIn login and save session cookies.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check if LinkedIn session is valid.",
    )
    args = parser.parse_args()

    if args.login:
        asyncio.run(_login())
        return

    if args.status:
        asyncio.run(_status())
        return

    # Start MCP server
    from linkedin_mcp_custom.server import create_mcp_server

    mcp = create_mcp_server()
    print("Starting linkedin-mcp-custom MCP server...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
