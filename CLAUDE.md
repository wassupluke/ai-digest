# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Digest: automated monthly AI/ML research digest generator. Fetches recent papers from arXiv (cs.AI, cs.SE), synthesizes them using Claude, and outputs self-contained React-based HTML pages.

## Running

```bash
# Generate a digest (requires ANTHROPIC_API_KEY env var)
python scripts/digest.py
```

Environment variables:
- `ANTHROPIC_API_KEY` — required
- `DIGEST_DAYS` — lookback window in days (default: 7)
- `DIGEST_CATEGORY` — `both`, `cs.AI`, or `cs.SE`

No build step, no tests, no linter configured.

## Architecture

**`scripts/digest.py`** — Single-file entry point. Sends a system prompt to Claude (Sonnet 4) with the `web_search` tool enabled. Claude fetches arXiv listings and Anthropic docs, filters relevant papers, and returns a self-contained React JSX component. The script extracts the JSX from the response, wraps it in an HTML shell (React 18 + Babel + Tailwind via CDN), writes to `docs/digests/YYYY-MM-DD.html`, and updates the index.

**`docs/index.html`** — Landing page. Digest links are injected at the `<!-- DIGESTS -->` marker by the script.

**`docs/digests/`** — Output directory for generated digest HTML files.

**`.github/workflows/monthly-digest.yml`** — GitHub Actions workflow. Runs on the 1st of each month via cron, also supports manual `workflow_dispatch` with configurable `days` and `category` inputs. Commits generated files back to the repo.
