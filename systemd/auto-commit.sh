#!/usr/bin/env bash
# Auto-commit and push the customs-penalties-cn repo every 5 minutes
# (only when there are real changes to tracked files).

set -euo pipefail

REPO="/volume1/SynologyDrive/lab/customs-penalties-cn"
cd "$REPO"

# Bail if nothing changed in tracked or untracked-not-ignored files
if [[ -z "$(git status --porcelain)" ]]; then
    exit 0
fi

# Build a short summary of what changed
SUMMARY=$(git status --porcelain | head -5 | sed 's/^/  /')
ROWS=$(ls -1 data/parsed/*.parquet 2>/dev/null | wc -l || true)

git add -A
git commit -m "auto: $(date -u +%Y-%m-%dT%H:%MZ) (${ROWS} parsed files)

Changed:
${SUMMARY}
" --quiet

if git remote get-url origin >/dev/null 2>&1; then
    git push --quiet 2>&1 || {
        echo "push failed at $(date -u)" >&2
        exit 1
    }
fi
