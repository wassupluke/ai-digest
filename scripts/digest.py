"""
digest.py — Weekly AI Research Digest Generator
Calls Claude with the digest system prompt, receives JSON paper data,
injects it into the HTML template, and writes to docs/digests/.
"""

import os
import re
import json
import glob
import datetime
import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DAYS    = int(os.environ.get("DIGEST_DAYS", "7"))
CATEGORY = os.environ.get("DIGEST_CATEGORY", "both")
TODAY   = datetime.date.today()
SLUG    = TODAY.isoformat()
SCRIPT_DIR = os.path.dirname(__file__)
OUT_DIR = os.path.join(SCRIPT_DIR, "..", "docs", "digests")
IDX     = os.path.join(SCRIPT_DIR, "..", "docs", "index.html")
TEMPLATE = os.path.join(SCRIPT_DIR, "..", "docs", "digest-template.html")

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# System prompt — instructs Claude to return JSON only
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = r"""
You are a research assistant that monitors recent AI and software engineering
papers and Anthropic documentation, then synthesizes actionable Claude
optimization guides.

When asked to run the digest, execute this workflow:

### Step 1 — Fetch Recent Papers
Fetch these arXiv listing pages using your web_search capability:
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

### Step 4 — Synthesize
For each qualifying paper, produce a JSON object with actionable steps and
fact-check verdicts. Each step should include a concrete code or prompt example.

### Step 5 — Fact-Check
Review each actionable step for accuracy. Set verdict to "pass" if the step
is well-supported by the paper's findings. Set verdict to "flag" with a
verdict_note explaining the concern if a step overstates the paper's findings.

### Step 6 — Output
Return ONLY a JSON array (no markdown fences, no explanation). Each element:
{
  "id": "2601.00086",
  "date": "Jan 2026",
  "title": "Paper Title",
  "url": "https://arxiv.org/abs/2601.00086",
  "category": "cs.AI",
  "technique": "short label",
  "tldr": "1-2 sentence summary",
  "implication": "What this means for Claude users (2-3 sentences)",
  "steps": [
    {
      "id": "s1",
      "text": "Actionable step description",
      "example": "code or prompt snippet",
      "verdict": "pass",
      "verdict_note": ""
    }
  ],
  "docs": [
    {"title": "Relevant doc page", "url": "https://docs.anthropic.com/..."}
  ]
}

CRITICAL: Return ONLY the JSON array. No text before or after. No markdown fences.
""".strip()


def build_user_message():
    cat_flag = ""
    if CATEGORY != "both":
        cat_flag = f" --cat {CATEGORY}"
    return f"/digest --days {DAYS}{cat_flag}"


# ---------------------------------------------------------------------------
# Call Claude with web search tool
# ---------------------------------------------------------------------------
def run_digest():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"[digest] Running for {SLUG}, days={DAYS}, cat={CATEGORY}")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=[
            {"type": "web_search_20250305", "name": "web_search"},
        ],
        messages=[{"role": "user", "content": build_user_message()}],
    )

    # Extract text content from the response
    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    text = text.strip()

    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # Find the JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in response:\n{text[:500]}")

    papers = json.loads(text[start:end + 1])
    print(f"[digest] Got {len(papers)} papers")
    return papers


# ---------------------------------------------------------------------------
# Inject data into template and write output
# ---------------------------------------------------------------------------
def write_page(papers: list):
    issue_number = len(glob.glob(os.path.join(OUT_DIR, "*.html"))) + 1

    digest_data = {
        "papers": papers,
        "date": SLUG,
        "issueNumber": issue_number,
    }

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()

    html = template.replace(
        "__DIGEST_DATA_PLACEHOLDER__",
        json.dumps(digest_data, ensure_ascii=False),
    )

    out_path = os.path.join(OUT_DIR, f"{SLUG}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[digest] Written → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Update the index page
# ---------------------------------------------------------------------------
def update_index(new_page_path: str):
    if not os.path.exists(IDX):
        print("[digest] No index.html found — skipping index update.")
        return

    with open(IDX, "r", encoding="utf-8") as f:
        content = f.read()

    entry = (
        f'<li><a href="digests/{SLUG}.html" class="digest-link">'
        f'Digest — {SLUG}</a></li>'
    )

    if "<!-- DIGESTS -->" in content:
        content = content.replace(
            "<!-- DIGESTS -->",
            f"<!-- DIGESTS -->\n      {entry}"
        )
        with open(IDX, "w", encoding="utf-8") as f:
            f.write(content)
        print("[digest] Index updated.")
    else:
        print("[digest] Warning: <!-- DIGESTS --> marker not found in index.html.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    papers = run_digest()

    if not papers:
        print("[digest] ERROR: Claude returned no papers.")
        raise SystemExit(1)

    path = write_page(papers)
    update_index(path)

    print("[digest] Done.")
