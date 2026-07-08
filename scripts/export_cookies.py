"""Export LinkedIn cookies from current browser session to JSON.

Usage:
    uv run python scripts/export_cookies.py

Output:
    Prints a JSON object to stdout. Copy this value to GitHub Secrets
    as LINKEDIN_COOKIES for the CI/CD workflow.
"""

import asyncio
import json
import sys

from patchright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(  # noqa: UP038
                __import__("pathlib").Path.home() / ".linkedin-mcp-custom" / "profile"
            ),
            headless=False,
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print("Navigating to linkedin.com/feed...", file=sys.stderr)
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        # Check if we're logged in
        if "/feed/" not in page.url:
            print("Not authenticated. Run --login first.", file=sys.stderr)
            await context.close()
            sys.exit(1)

        # Get cookies filtered to LinkedIn domain
        all_cookies = await context.cookies()
        linkedin_cookies = [c for c in all_cookies if "linkedin" in c.get("domain", "")]
        print(json.dumps(linkedin_cookies, indent=2))
        print(f"\nExported {len(linkedin_cookies)} LinkedIn cookies", file=sys.stderr)

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
