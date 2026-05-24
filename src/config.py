from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
LOG_DIR = PROJECT_ROOT / "logs"

GACC_BASE = "http://www.customs.gov.cn"
GACC_PENALTY_INDEX = f"{GACC_BASE}/customs/xxgk55/xz74/3076200/index.html"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)

REQUEST_DELAY_S = 2.0
MAX_LIST_PAGES_PER_RUN = 20
NAV_TIMEOUT_MS = 60_000
