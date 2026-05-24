"""Headless-Chromium scrape of GACC penalty disclosure pages.

Strategy:
1. Launch Chromium, navigate to the penalty index. The site sets the $_ts
   anti-bot cookie after a JS challenge.
2. Once the index renders, harvest detail-page URLs from the listing.
3. For each detail page (still in the same browser context, reusing cookies),
   fetch raw HTML and save under data/raw/<run_date>/.
4. Walk pagination up to MAX_LIST_PAGES_PER_RUN.

Output layout:
  data/raw/<YYYY-MM-DD>/
    index/page_001.html
    index/page_002.html
    ...
    detail/<sha1-of-url>.html
    manifest.jsonl   # one record per file with url, fetch_ts, sha1, file
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page

from config import (
    GACC_PENALTY_INDEX,
    GACC_BASE,
    MAX_LIST_PAGES_PER_RUN,
    NAV_TIMEOUT_MS,
    RAW_DIR,
    REQUEST_DELAY_S,
    USER_AGENT,
)

log = logging.getLogger("scrape")


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _today_dir() -> Path:
    d = RAW_DIR / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (d / "index").mkdir(parents=True, exist_ok=True)
    (d / "detail").mkdir(parents=True, exist_ok=True)
    return d


async def _save_page(page: Page, url: str, out: Path) -> dict:
    html = await page.content()
    out.write_text(html, encoding="utf-8")
    return {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha1": _sha1(html),
        "size": len(html),
        "file": str(out.relative_to(RAW_DIR.parent.parent)),
    }


async def _extract_detail_links(page: Page) -> list[str]:
    """GACC penalty list items use anchors under the article-list container."""
    anchors = await page.eval_on_selector_all(
        "a",
        "els => els.map(e => ({href: e.getAttribute('href'), text: e.innerText}))",
    )
    out: list[str] = []
    for a in anchors:
        href = a.get("href") or ""
        text = (a.get("text") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if any(skip in href.lower() for skip in ("mailto:", "tel:")):
            continue
        # Heuristic: detail pages on customs.gov.cn end with .html under a yyyy/mm/ path
        if href.endswith(".html") and ("/xxgk55/" in href or "Info" in href) and text:
            out.append(urljoin(page.url, href))
    seen = set()
    deduped = []
    for u in out:
        if u not in seen and u != page.url:
            seen.add(u)
            deduped.append(u)
    return deduped


async def _next_page_url(page: Page) -> str | None:
    """List pagination on customs.gov.cn uses ?pageNum= or location.href tricks."""
    candidates = await page.eval_on_selector_all(
        "a",
        "els => els.filter(e => /下一页|下页|next/i.test(e.innerText)).map(e => e.getAttribute('href'))",
    )
    for href in candidates:
        if href and not href.startswith("javascript:"):
            return urljoin(page.url, href)
    return None


async def run() -> dict:
    run_dir = _today_dir()
    manifest_path = run_dir / "manifest.jsonl"
    manifest = manifest_path.open("a", encoding="utf-8")
    stats = {"list_pages": 0, "detail_pages": 0, "errors": 0, "start": datetime.now(timezone.utc).isoformat()}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await browser.new_context(
            user_agent=USER_AGENT,
            locale="zh-CN",
            viewport={"width": 1366, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        seen_detail: set[str] = set()
        current_url: str | None = GACC_PENALTY_INDEX
        page_idx = 0

        while current_url and page_idx < MAX_LIST_PAGES_PER_RUN:
            page_idx += 1
            log.info("LIST %02d %s", page_idx, current_url)
            try:
                await page.goto(current_url, wait_until="domcontentloaded")
                # Give the JS challenge a moment to settle on first load.
                await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
            except Exception as e:
                log.error("nav failed: %s", e)
                stats["errors"] += 1
                break

            list_file = run_dir / "index" / f"page_{page_idx:03d}.html"
            rec = await _save_page(page, current_url, list_file)
            manifest.write(json.dumps({"kind": "index", **rec}, ensure_ascii=False) + "\n")
            manifest.flush()
            stats["list_pages"] += 1

            details = await _extract_detail_links(page)
            log.info("  found %d candidate detail links", len(details))

            for du in details:
                if du in seen_detail:
                    continue
                seen_detail.add(du)
                try:
                    await asyncio.sleep(REQUEST_DELAY_S)
                    await page.goto(du, wait_until="domcontentloaded")
                    await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
                    detail_file = run_dir / "detail" / f"{_sha1(du)}.html"
                    drec = await _save_page(page, du, detail_file)
                    manifest.write(json.dumps({"kind": "detail", **drec}, ensure_ascii=False) + "\n")
                    manifest.flush()
                    stats["detail_pages"] += 1
                except Exception as e:
                    log.warning("detail fail %s: %s", du, e)
                    stats["errors"] += 1

            try:
                await page.goto(current_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
                current_url = await _next_page_url(page)
            except Exception as e:
                log.warning("pagination fail: %s", e)
                current_url = None
            await asyncio.sleep(REQUEST_DELAY_S)

        await ctx.close()
        await browser.close()

    stats["end"] = datetime.now(timezone.utc).isoformat()
    manifest.close()
    (run_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("DONE %s", stats)
    return stats


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    stats = asyncio.run(run())
    return 0 if stats["list_pages"] > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
