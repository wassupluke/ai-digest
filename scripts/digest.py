"""
digest.py — Weekly AI Research Digest Generator
Calls Claude with the digest system prompt, extracts the JSX/HTML artifact,
wraps it in a self-contained HTML page, and writes it to docs/digests/.
"""

import os
import re
import json
import datetime
import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DAYS    = int(os.environ.get("DIGEST_DAYS", "7"))
CATEGORY = os.environ.get("DIGEST_CATEGORY", "both")
TODAY   = datetime.date.today()
SLUG    = TODAY.isoformat()                          # e.g. 2025-06-23
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "digests")
IDX     = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# System prompt — the full digest instructions live here
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = r"""
You are a research assistant that monitors recent AI and software engineering
papers and Anthropic documentation, then synthesizes actionable Claude
optimization guides.

When asked to run the digest, execute this workflow:

### Step 1 — Fetch Recent Papers
Fetch these arXiv listing pages using your web_search / web_fetch capability:
  https://arxiv.org/list/cs.AI/recent
  https://arxiv.org/list/cs.SE/recent

Extract papers from the last DAYS days (up to 15 per category).
Record: title, arXiv ID, submission date, abstract.

### Step 2 — Fetch Anthropic Documentation
Fetch key pages from:
  https://docs.anthropic.com
  https://docs.claude.ai
  https://support.claude.ai
  https://github.com/anthropics/claude-code

### Step 3 — Relevance Screening
Keep only papers relevant to: LLM behavior, prompting, agents, code
generation, reasoning, retrieval, context management, tool use, evaluation,
fine-tuning, alignment, or human-AI collaboration AND applicable to Claude users.

### Step 4 — Synthesize Guides
For each qualifying paper produce a guide section:
  ## [Paper Title]
  **arXiv:** [ID] | [URL]
  **TL;DR:** [1-2 sentences]
  ### What this means for Claude users
  [2-3 sentences]
  ### Actionable Steps
  1. ...
  2. ...
  ### Supporting Docs
  - [title] → [URL]
  ### Example
  ```
  [prompt or API snippet]
  ```

### Step 5 — Fact-Check
After drafting, review each actionable step for accuracy. Flag any step that
overstates the paper's findings and revise it.

### Step 6 — Output
Return a SINGLE self-contained React component (default export) that renders
the full digest as a beautiful, readable web page. Use only inline Tailwind
classes (loaded via CDN). Do NOT import any local modules. The component must
be renderable with ReactDOM.render in a browser with React + Babel loaded from
CDN. Structure: summary table at top, guide sections, fact-check log, docs index.

IMPORTANT: Your entire response should be just the JSX component — no markdown
fences, no explanation before or after. Start with `function Digest()` and end
with `export default Digest;`.
""".strip()


def build_user_message():
    cat_flag = ""
    if CATEGORY != "both":
        cat_flag = f" --cat {CATEGORY}"
    return f"/digest --days {DAYS}{cat_flag}"


# ---------------------------------------------------------------------------
# Call Claude with extended thinking + web search tool
# ---------------------------------------------------------------------------
def run_digest():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"[digest] Running for {SLUG}, days={DAYS}, cat={CATEGORY}")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[
            {"type": "web_search_20250305", "name": "web_search"},
        ],
        messages=[{"role": "user", "content": build_user_message()}],
    )

    # Extract text content from the response (may follow tool use blocks)
    jsx = ""
    for block in response.content:
        if block.type == "text":
            jsx += block.text

    jsx = jsx.strip()

    # Strip any accidental markdown fences
    jsx = re.sub(r"^```[a-z]*\n?", "", jsx, flags=re.MULTILINE)
    jsx = re.sub(r"\n?```$", "", jsx, flags=re.MULTILINE)
    jsx = jsx.strip()

    # Extract only the JS/JSX code — strip any conversational preamble
    match = re.search(r"(function\s+Digest\s*\()", jsx)
    if match:
        jsx = jsx[match.start():]

    # Remove duplicate "export default Digest;" and "ReactDOM.render(...)"
    # since the HTML shell already includes the ReactDOM.render call
    jsx = re.sub(r"\bexport\s+default\s+Digest\s*;?", "", jsx)
    jsx = re.sub(r"ReactDOM\.render\s*\(.*?\)\s*;?", "", jsx, flags=re.DOTALL)
    jsx = jsx.strip()

    return jsx


# ---------------------------------------------------------------------------
# Wrap JSX in a standalone HTML file (React + Babel via CDN)
# ---------------------------------------------------------------------------
HTML_SHELL = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Research Digest — {slug}</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.2/babel.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet" />
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
{jsx}

ReactDOM.render(<Digest />, document.getElementById('root'));
  </script>
</body>
</html>
"""


def write_page(jsx: str):
    html = HTML_SHELL.format(slug=SLUG, jsx=jsx)
    out_path = os.path.join(OUT_DIR, f"{SLUG}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[digest] Written → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Update the index page
# ---------------------------------------------------------------------------
def update_index(new_page_path: str):
    """Inject a new entry into the index page's digest list."""
    if not os.path.exists(IDX):
        print("[digest] No index.html found — skipping index update.")
        return

    with open(IDX, "r", encoding="utf-8") as f:
        content = f.read()

    entry = (
        f'<li><a href="digests/{SLUG}.html" class="digest-link">'
        f'Digest — {SLUG}</a></li>'
    )

    # Expects a <!-- DIGESTS --> marker in your index.html
    if "<!-- DIGESTS -->" in content:
        content = content.replace(
            "<!-- DIGESTS -->",
            f"<!-- DIGESTS -->\n      {entry}"
        )
        with open(IDX, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[digest] Index updated.")
    else:
        print("[digest] Warning: <!-- DIGESTS --> marker not found in index.html.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    jsx = run_digest()

    if not jsx:
        print("[digest] ERROR: Claude returned no JSX content.")
        raise SystemExit(1)

    write_page(jsx)
    update_index(os.path.join(OUT_DIR, f"{SLUG}.html"))

    print("[digest] Done.")
