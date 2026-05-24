# customs-penalties-cn — project state notes

> Saved to the NAS so any machine can resume the project. This file lives inside the team folder and syncs back via Syncthing.

## Goal
Daily scraper for **China Customs administrative penalty announcements** (海关行政处罚) — accumulating a daily-frequency panel of customs enforcement actions (firm names, violation type, amounts, dates) that is not currently maintained by any commercial data vendor. Intended as a unique research dataset for trade-economics papers (smuggling, tariff evasion, misinvoicing, transshipment).

Rationale: see "Tier 1 — Genuinely AER/QJE/JPE-grade" discussion in the planning conversation. **Almost no econ exploitation** yet, perfectly complements gravity/Comtrade research.

## Where it lives
- Project root: `/volume1/SynologyDrive/lab/customs-penalties-cn/` (NAS-synced via Syncthing folder `synology-drive`)
- VPS replica also at `/volume1/SynologyDrive/lab/customs-penalties-cn/` (same path)
- Git repo (local): inside the project root
- Git remote: **not yet set** — pending user's GitHub username + `gh auth login`

## Architecture
- **Lang**: Python 3.11+ managed by `uv` (`pyproject.toml`, `uv.lock` checked in)
- **Scraper**: Playwright headless Chromium (`src/scrape.py`)
- **Parser**: BeautifulSoup4 + lxml + regex (`src/parse.py`)
- **Entrypoint**: `src/run_daily.py` (scrape → parse → write summary)
- **Smoke test**: `src/smoke.py` (single-page probe to verify JS-challenge bypass)
- **Storage**:
  - Raw HTML snapshots → `data/raw/<YYYY-MM-DD>/{index,detail}/*.html` (NOT in git — too large; only on NAS)
  - Parsed records → `data/parsed/penalties_<YYYY-MM-DD>.parquet` (IS in git — small)
  - Logs → `logs/` (NOT in git)
  - Manifest → `data/raw/<date>/manifest.jsonl` (per-file record of url + sha1 + size)
- **Schedule**: systemd user timer `customs-penalties.timer` fires daily at 03:30 UTC (~+10 min random jitter)
- **Auto-commit**: systemd user timer `customs-penalties-autocommit.timer` runs `systemd/auto-commit.sh` every 5 min to commit + push code/parsed changes (paused until git remote is set)

## Current state (as of 2026-05-24)
- ✅ Project skeleton + scraper code + parser + run_daily entrypoint
- ✅ pyproject.toml + uv.lock committed
- ✅ Playwright + Chromium installed (~350 MB on VPS, cache at `~/.cache/ms-playwright/`)
- ✅ Initial git commit (~12 files, 320K)
- ✅ Daily timer enabled + lingering enabled (`loginctl enable-linger admin`)
- ⏸ Auto-commit timer NOT yet enabled (waiting for git remote)
- ⛔ **Smoke test FAILING**: Playwright defeats the JS challenge partially (cookies set), but the second request returns HTTP 400 — fingerprint detection.
  - Confirmed: 412 → JS challenge → cookies set → retry returns 400.
  - Likely cause: headless Chromium fingerprint + German VPS IP being treated as suspicious by the GACC anti-bot.

## Blocking issue: anti-bot defeats headless from German IP
The customs.gov.cn JavaScript challenge (Jiasule on top of Akamai) is more sophisticated than basic cookie-set challenges. It detects headless browser fingerprints and returns 400 on the retry submission.

### Things tried so far
1. ❌ Plain Playwright headless Chromium → 412 (JS challenge) → 400 on retry (fingerprint detected)
2. ❌ `playwright-stealth` plugin → same 412 → 400 pattern. Stealth patches don't defeat this particular challenge.

### Things still to try (in order of effort)
1. **`rebrowser-playwright`** — heavier patched Playwright fork. Often works on harder challenges. Worth one more try.
2. **Use full Chromium build** (not headless-shell) with `headless="new"` and `--disable-blink-features=AutomationControlled`. Cheap; uncertain.
3. **Add a Chinese-egress proxy** — would address geoblocking suspicion. Cost + complexity. (~$10-30/mo for a small proxy, or Tailscale exit node in HK/Singapore.)
4. **Use Wayback Machine snapshots** — `web.archive.org/web/<date>/customs.gov.cn/...` — wayback regularly crawls; we lose real-time daily granularity but can backfill. Combine with a low-frequency direct scrape attempt.
5. **Pivot to an alternative source** with weaker/no anti-bot:
   - **`sf.taobao.com`** — judicial auctions (Alibaba; usually friendlier)
   - **`tousu.sina.com.cn`** — Black Cat consumer complaints (Sina; usually friendlier)
   - **Hong Kong Customs & Excise** — fully open, no anti-bot, publishes seizure & penalty data
   - **US CBP (Customs and Border Protection)** — public JSON/CSV downloads of enforcement actions
   - Other provincial 海关 sub-sites — some are on the same anti-bot, some are not

## Resume instructions
On any machine that has the synced team folder mounted at `/volume1/SynologyDrive/lab/customs-penalties-cn/` (or equivalent path):

```bash
cd /path/to/customs-penalties-cn
uv sync
uv run playwright install chromium
uv run python src/smoke.py   # verify scrape works
```

Then either:
- continue debugging the anti-bot (see "Things to try" above), or
- switch the project's `GACC_PENALTY_INDEX` (in `src/config.py`) to a different source URL.

## Git remote setup (when ready)
```bash
gh auth login                                # interactive, user-driven
gh repo create customs-penalties-cn --private --source=. --push
systemctl --user enable --now customs-penalties-autocommit.timer
```

## Files in git
```
.gitignore
pyproject.toml
uv.lock
src/config.py
src/scrape.py
src/parse.py
src/smoke.py
src/run_daily.py
systemd/customs-penalties.service
systemd/customs-penalties.timer
systemd/customs-penalties-autocommit.service
systemd/customs-penalties-autocommit.timer
systemd/auto-commit.sh
PROJECT_NOTES.md   # this file
```

## Files intentionally NOT in git
- `data/raw/` — HTML snapshots, can grow to GB. Source of truth = NAS.
- `data/parsed/` is in git (small Parquet daily files).
- `logs/`, `.venv/`, `__pycache__/`, `.uv-cache/`.
