"""Quick smoke test: can Playwright get past the customs.gov.cn JS challenge
and load the actual penalty list HTML? Prints the page title and any anchor
hrefs that look like penalty detail links.
"""

import asyncio
import sys
from playwright.async_api import async_playwright

from config import GACC_PENALTY_INDEX, USER_AGENT, NAV_TIMEOUT_MS


async def main() -> int:
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = await b.new_context(user_agent=USER_AGENT, locale="zh-CN",
                                  viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        print(f"GET {GACC_PENALTY_INDEX}", flush=True)
        await page.goto(GACC_PENALTY_INDEX, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
        except Exception as e:
            print(f"networkidle wait timed out: {e}", flush=True)

        title = await page.title()
        url = page.url
        html = await page.content()
        print(f"final url:  {url}", flush=True)
        print(f"page title: {title!r}", flush=True)
        print(f"html bytes: {len(html)}", flush=True)
        print(f"has '海关': {'海关' in html}", flush=True)
        print(f"has '处罚': {'处罚' in html}", flush=True)
        print(f"has '$_ts' (still on challenge): {'$_ts' in html}", flush=True)

        anchors = await page.eval_on_selector_all(
            "a",
            "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim()])",
        )
        candidate = [(h, t) for h, t in anchors if h and h.endswith(".html") and t]
        print(f"anchors total: {len(anchors)}, html-ending: {len(candidate)}")
        for h, t in candidate[:12]:
            print(f"  - {t[:40]!r:42s} -> {h}")

        await b.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
