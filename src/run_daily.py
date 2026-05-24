"""Daily entrypoint: scrape, then parse, then write a run summary."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

from config import LOG_DIR
from scrape import run as scrape_run
from parse import parse_run_dir
from config import RAW_DIR, PARSED_DIR


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{today}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("daily")

    log.info("=== run start %s ===", today)
    scrape_stats = asyncio.run(scrape_run())

    df = parse_run_dir(RAW_DIR / today)
    if df.empty:
        log.warning("no detail rows parsed")
    else:
        out = PARSED_DIR / f"penalties_{today}.parquet"
        df.to_parquet(out, index=False)
        log.info("parsed %d rows -> %s", len(df), out)

    summary = {
        "date": today,
        **scrape_stats,
        "rows_parsed": int(len(df)),
    }
    (LOG_DIR / f"{today}.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("=== run done: %s ===", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
