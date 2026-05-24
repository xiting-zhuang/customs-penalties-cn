"""Parse raw detail HTML files into a structured Parquet panel.

We don't fully know the schema yet — GACC penalty pages vary slightly in
layout across customs districts. The parser extracts what it can recognize
and dumps the rest as `raw_text` for later improvement.

Run: `uv run python src/parse.py`
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from config import PARSED_DIR, RAW_DIR

log = logging.getLogger("parse")

# Common Chinese fields in GACC penalty announcements
FIELD_PATTERNS = {
    "case_no": re.compile(r"(?:行政处罚决定书文号|决定书文号|文书号|案号)[:：]?\s*([\w\-（）()]+)"),
    "respondent": re.compile(r"(?:当事人|被处罚人|受处罚单位|企业名称|姓名)[:：]?\s*([^\s。;；]{2,80})"),
    "violation": re.compile(r"(?:违法事实|主要违法事实|违法行为类型|案由)[:：]?\s*([^。]{2,500})"),
    "penalty": re.compile(r"(?:处罚内容|行政处罚的种类和依据|处罚决定|处罚结果)[:：]?\s*([^。]{2,500})"),
    "decision_date": re.compile(r"(?:决定日期|处罚决定日期|作出决定日期)[:：]?\s*(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})"),
    "authority": re.compile(r"(?:执法机关|作出决定机关|处罚机关|海关单位)[:：]?\s*([^\s。]{2,40})"),
}


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    # Strip nav/header/footer noise
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()

    title = (soup.title.text.strip() if soup.title else "") or ""
    body = soup.find("body")
    text = (body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True))

    rec: dict = {"title": title, "raw_text": text}
    for field, pat in FIELD_PATTERNS.items():
        m = pat.search(text)
        rec[field] = m.group(1).strip() if m else None

    return rec


def parse_run_dir(run_dir: Path) -> pd.DataFrame:
    manifest = run_dir / "manifest.jsonl"
    if not manifest.exists():
        return pd.DataFrame()

    rows = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") != "detail":
            continue
        file_path = RAW_DIR.parent.parent / rec["file"]
        if not file_path.exists():
            continue
        try:
            html = file_path.read_text(encoding="utf-8")
            parsed = parse_detail(html)
            parsed.update({
                "url": rec["url"],
                "fetched_at": rec["fetched_at"],
                "sha1": rec["sha1"],
                "file": rec["file"],
            })
            rows.append(parsed)
        except Exception as e:
            log.warning("parse fail %s: %s", file_path, e)
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = RAW_DIR / today
    if not run_dir.exists():
        log.error("no raw dir for today: %s", run_dir)
        return 2
    df = parse_run_dir(run_dir)
    if df.empty:
        log.warning("no detail records parsed")
        return 3
    out = PARSED_DIR / f"penalties_{today}.parquet"
    df.to_parquet(out, index=False)
    log.info("wrote %d rows to %s", len(df), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
