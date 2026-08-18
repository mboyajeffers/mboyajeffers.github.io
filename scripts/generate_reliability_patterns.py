#!/usr/bin/env python3
"""
Generates reliability-patterns/**  from the live public repo
github.com/mboyajeffers/pipeline-reliability-patterns.

This is the mechanism, not just a claim, that keeps the site pages from drifting
stale relative to the repo: every run clones the repo's current `main` fresh,
runs its real test suite, and renders pages directly from that content. There is
no second hand-maintained copy of any pipeline's README/BUILD_LOG/code to forget
to update -- the repo is the only source, and this script is idempotent over it.

Run on a schedule + workflow_dispatch by .github/workflows/reliability_patterns.yml,
same pattern as scripts/generate_dashboard.py / market-pulse.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

SITE_ROOT = Path(__file__).parent.parent
OUT_ROOT = SITE_ROOT / "reliability-patterns"
BUILD_DIR = SITE_ROOT / "_reliability_patterns_source"  # gitignored, ephemeral clone
REPO_URL = "https://github.com/mboyajeffers/pipeline-reliability-patterns"

PIPELINES = ["finance", "crypto", "ecommerce", "solar"]

CODE_STYLE = "monokai"
PYGMENTS_CSS = HtmlFormatter(style=CODE_STYLE).get_style_defs(".highlight")

MD_EXTENSIONS = ["tables", "fenced_code", "codehilite", "toc"]
MD_EXT_CONFIG = {"codehilite": {"css_class": "highlight", "pygments_style": CODE_STYLE, "guess_lang": False}}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def clone_source_repo() -> str:
    """Fresh shallow clone every run. Returns the current commit SHA."""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    run(["git", "clone", "--depth", "1", REPO_URL, str(BUILD_DIR)])
    sha = run(["git", "rev-parse", "HEAD"], cwd=BUILD_DIR).stdout.strip()
    return sha


def run_pipeline_tests(pipeline: str) -> str:
    """Runs the real test suite for one pipeline and returns the actual captured
    output -- this is what gets embedded on the page, not a hand-written claim.
    """
    result = run(
        [sys.executable, "-m", "pytest", f"pipelines/{pipeline}/tests", "-v", "--no-header"],
        cwd=BUILD_DIR,
        check=False,
    )
    return (result.stdout + result.stderr).strip()


def md_to_html(path: Path) -> str:
    text = path.read_text()
    return markdown.markdown(text, extensions=MD_EXTENSIONS, extension_configs=MD_EXT_CONFIG)


def code_to_html(path: Path) -> str:
    from pygments import highlight
    from pygments.lexers import PythonLexer

    code = path.read_text()
    formatter = HtmlFormatter(style=CODE_STYLE, cssclass="highlight")
    return highlight(code, PythonLexer(), formatter)


BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@Mboya_Jeffers">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {{
    --bg-primary: #16181d;
    --bg-secondary: #1b1e24;
    --bg-card: #1f232a;
    --accent: #6fae9c;
    --accent-hover: #82c0ae;
    --accent-soft: rgba(111, 174, 156, 0.14);
    --border: #2a2f38;
    --text: #e6e8eb;
    --text-dim: #9aa1ab;
}}
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    background: var(--bg-primary);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
}}
.mono {{ font-family: 'Space Mono', monospace; }}
nav {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 1.25rem 2rem; border-bottom: 1px solid var(--border);
    max-width: 960px; margin: 0 auto;
}}
nav a {{ color: var(--text); text-decoration: none; font-weight: 600; }}
nav .nav-links a {{ color: var(--text-dim); margin-left: 1.5rem; font-weight: 500; font-size: 0.9rem; }}
nav .nav-links a:hover {{ color: var(--accent-hover); }}
main {{ max-width: 960px; margin: 0 auto; padding: 2.5rem 2rem 4rem; }}
h1 {{ font-size: 2rem; margin-bottom: 0.25rem; }}
h2 {{ font-size: 1.35rem; margin-top: 2.5rem; border-top: 1px solid var(--border); padding-top: 1.75rem; }}
h3 {{ font-size: 1.05rem; color: var(--accent-hover); }}
a {{ color: var(--accent-hover); }}
.subtitle {{
    color: var(--text-dim); margin: 0 auto 1.75rem; max-width: 700px; text-align: center;
}}
.badge-row {{
    display: flex; gap: 1.5rem; align-items: center; justify-content: center;
    margin: 1.5rem 0 3rem; flex-wrap: wrap;
}}
.badge-row img {{ height: 20px; }}
.pill {{
    display: inline-block; background: var(--accent-soft); color: var(--accent-hover);
    border-radius: 999px; padding: 0.35rem 1rem; font-size: 0.8rem; font-family: 'Space Mono', monospace;
}}
.card {{
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.5rem; margin: 1.25rem 0;
}}
.card.tile {{ padding: 2rem 1.75rem; text-align: center; }}
.card.tile h3 {{ margin-bottom: 0.5rem; }}
.card a.card-link {{ text-decoration: none; color: inherit; display: block; }}
.card a.card-link:hover {{ border-color: var(--accent); }}
.grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 300px));
    gap: 1.75rem; justify-content: center; margin: 0 auto;
}}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.92rem; }}
th {{ color: var(--text-dim); font-weight: 600; }}
code {{ font-family: 'Space Mono', monospace; background: var(--bg-secondary); padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.9em; }}
pre {{ overflow-x: auto; border-radius: 8px; padding: 1rem; border: 1px solid var(--border); }}
pre code {{ background: none; padding: 0; }}
.test-output {{
    background: #0d0f12; border: 1px solid var(--border); border-radius: 8px;
    padding: 1rem; overflow-x: auto; font-family: 'Space Mono', monospace; font-size: 0.82rem;
    color: #c7d0da; white-space: pre-wrap;
}}
.test-output .pass {{ color: #7ee0a8; }}
footer {{ border-top: 1px solid var(--border); padding: 2rem; text-align: center; color: var(--text-dim); font-size: 0.85rem; }}
footer a {{ color: var(--text-dim); margin: 0 0.5rem; }}
{pygments_css}
</style>
</head>
<body>
<nav>
    <a href="/">Mboya Jeffers</a>
    <ul class="nav-links" style="list-style:none; display:flex; margin:0; padding:0;">
        <li><a href="/reliability-patterns/">Reliability Patterns</a></li>
        <li><a href="/market-pulse/">Market Pulse</a></li>
        <li><a href="https://github.com/mboyajeffers/pipeline-reliability-patterns" target="_blank" rel="noopener">Source</a></li>
    </ul>
</nav>
<main>
{content}
</main>
<footer>
    <div>© 2026 Mboya Jeffers</div>
    <div style="margin-top:0.5rem;">
        <a href="https://github.com/mboyajeffers" target="_blank" rel="noopener">GitHub</a>
        <a href="https://linkedin.com/in/mboya-jeffers-6377ba325" target="_blank" rel="noopener">LinkedIn</a>
        <a href="https://x.com/Mboya_Jeffers" target="_blank" rel="noopener">X</a>
        <a href="mailto:mboyajeffers9@gmail.com">Email</a>
    </div>
</footer>
</body>
</html>
"""


SITE_BASE = "https://mboyajeffers.github.io"


def render_page(title: str, description: str, content: str, url: str, image: str) -> str:
    return BASE_TEMPLATE.format(
        title=title, description=description, content=content,
        pygments_css=PYGMENTS_CSS, url=url, image=image,
    )


def build_index(sha: str) -> None:
    cards = ""
    for p in PIPELINES:
        cards += f"""<div class="card tile"><a class="card-link" href="/reliability-patterns/{p}/">
            <h3>{p.capitalize()} Pipeline</h3>
            <p class="subtitle" style="margin-bottom:0;">2 realistic production issues found, fixed, and test-pinned. Full postmortem-style build log.</p>
        </a></div>"""

    content = f"""
<h1>Pipeline Reliability Patterns</h1>
<p class="subtitle">Four small, real, runnable data pipelines — each built to demonstrate specific engineering judgment
under failure: the actual production failure modes these verticals hit, found, fixed, tested, and logged like a real
incident review. Every issue is proven twice by <code>pytest</code>, not claimed in prose.</p>
<div class="badge-row">
    <img src="https://github.com/mboyajeffers/pipeline-reliability-patterns/actions/workflows/ci.yml/badge.svg" alt="CI status">
    <span class="pill">commit {sha[:7]}</span>
    <span class="pill">generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</span>
</div>
<div class="grid">{cards}</div>
<h2>What's being screened for</h2>
<p>This isn't just "does it work" — it's built against a rubric a staff/lead engineer actually uses to evaluate a
candidate's code. See the <a href="/reliability-patterns/rubric/">full evaluation rubric</a> — 9 points, each mapped to
where it's demonstrated across these 4 pipelines.</p>
<p><a href="https://github.com/mboyajeffers/pipeline-reliability-patterns">Clone the source repo →</a> and run
<code>pytest -v</code> yourself — this page is generated directly from it, on every update, so nothing here can drift
from what's actually in the repo.</p>
"""
    write(OUT_ROOT / "index.html", render_page(
        "Pipeline Reliability Patterns — Mboya Jeffers",
        "Four real pipelines, 8 realistic production failure modes found, fixed, and test-pinned.",
        content,
        url=f"{SITE_BASE}/reliability-patterns/",
        image=f"{SITE_BASE}/assets/og/reliability-patterns-index.png",
    ))


def build_rubric() -> None:
    rubric_html = md_to_html(BUILD_DIR / "EVALUATION_RUBRIC.md")
    content = f"<div class='card'>{rubric_html}</div>"
    write(OUT_ROOT / "rubric" / "index.html", render_page(
        "Evaluation Rubric — Pipeline Reliability Patterns",
        "The 9-point rubric this repo is built to satisfy, and where each point is demonstrated.",
        content,
        url=f"{SITE_BASE}/reliability-patterns/rubric/",
        image=f"{SITE_BASE}/assets/og/reliability-patterns-index.png",
    ))


def build_pipeline_page(pipeline: str, sha: str) -> None:
    pdir = BUILD_DIR / "pipelines" / pipeline
    readme_html = md_to_html(pdir / "README.md")
    build_log_html = md_to_html(pdir / "BUILD_LOG.md")
    test_output = run_pipeline_tests(pipeline)

    before_files = sorted((pdir / "before").glob("*.py"))
    before_files = [f for f in before_files if f.name != "__init__.py"]
    before_html = "".join(
        f"<h3>Before — <code>{f.relative_to(BUILD_DIR)}</code></h3>{code_to_html(f)}" for f in before_files
    )
    after_html = code_to_html(pdir / "pipeline.py")

    content = f"""
<p><a href="/reliability-patterns/">&larr; All pipelines</a></p>
<h1>{pipeline.capitalize()} Pipeline</h1>
<div class="badge-row">
    <img src="https://github.com/mboyajeffers/pipeline-reliability-patterns/actions/workflows/ci.yml/badge.svg" alt="CI status">
    <span class="pill">commit {sha[:7]}</span>
    <a href="https://github.com/mboyajeffers/pipeline-reliability-patterns/tree/main/pipelines/{pipeline}" target="_blank" rel="noopener">View source on GitHub →</a>
</div>
<div class="card">{readme_html}</div>

<h2>Build Log — the postmortem</h2>
{build_log_html}

<h2>Before → After</h2>
<p class="subtitle">The pre-fix code is kept in the repo (not deleted) so this is checkable, not just asserted.</p>
{before_html}
<h3>After — <code>pipelines/{pipeline}/pipeline.py</code> (the fix, current on <code>main</code>)</h3>
{after_html}

<h2>Test output — proof, not a claim</h2>
<p class="subtitle">Real <code>pytest -v</code> output from this exact commit, captured when this page was generated.
<code>xfail</code> lines prove the bug is real against the pre-fix code; <code>PASSED</code> lines prove the fix.</p>
<pre class="test-output">{test_output}</pre>
"""
    write(OUT_ROOT / pipeline / "index.html", render_page(
        f"{pipeline.capitalize()} Pipeline — Reliability Patterns",
        f"Real production failure modes found, fixed, and test-pinned in a {pipeline} data pipeline.",
        content,
        url=f"{SITE_BASE}/reliability-patterns/{pipeline}/",
        image=f"{SITE_BASE}/assets/og/reliability-patterns-{pipeline}.png",
    ))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"wrote {path.relative_to(SITE_ROOT)}")


def main() -> None:
    sha = clone_source_repo()
    print(f"cloned pipeline-reliability-patterns @ {sha}")
    build_index(sha)
    build_rubric()
    for p in PIPELINES:
        build_pipeline_page(p, sha)
    shutil.rmtree(BUILD_DIR)
    print("done")


if __name__ == "__main__":
    main()
