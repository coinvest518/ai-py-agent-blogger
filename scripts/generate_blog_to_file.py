"""Generate a full blog post and save to HTML and Markdown-like files.

Usage:
  python scripts/generate_blog_to_file.py            # use real LLM (requires keys)
  python scripts/generate_blog_to_file.py --mock   # use canned output (no keys required)
  python scripts/generate_blog_to_file.py --out-dir ./tmp --format md,html

The script calls `generate_blog_content()` and writes two files:
  - {out_dir}/blog_output.html  (full HTML)
  - {out_dir}/blog_output.md    (markdown-like text)

This is a dev helper so you can inspect the exact article produced by the agent.
"""
from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path
from typing import Optional

# Import the generator (package-style import assumes you ran `pip install -e .`)
try:
    from agent.blog_email_agent import generate_blog_content
except Exception:
    # fallback to src import when running from repo without editable install
    from src.agent.blog_email_agent import generate_blog_content


SAMPLE_TREND = (
    "AI automation trends show 300% increase in small business adoption. "
    "Workflow automation saves 15+ hours per week for entrepreneurs. "
    "Tools like AI assistants and automated marketing are revolutionizing how small businesses operate."
)


def html_to_markdown_like(html_text: str) -> str:
    """Create a simple markdown-like extraction from HTML for quick viewing.

    This is intentionally lightweight (header -> #, <p> -> newline, strip other tags).
    """
    s = html_text
    # Convert heading tags to markdown headers
    s = re.sub(r"(?is)<h1[^>]*>(.*?)</h1>", r"# \1\n\n", s)
    s = re.sub(r"(?is)<h2[^>]*>(.*?)</h2>", r"## \1\n\n", s)
    s = re.sub(r"(?is)<h3[^>]*>(.*?)</h3>", r"### \1\n\n", s)
    # Convert paragraphs to double newlines
    s = re.sub(r"(?is)<p[^>]*>(.*?)</p>", r"\1\n\n", s)
    # Convert <li> to list items
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>", r"- \1\n", s)
    # Remove any remaining tags
    s = re.sub(r"<[^>]+>", "", s)
    # Unescape HTML entities and normalize whitespace
    s = html.unescape(s)
    s = re.sub(r"\n\s+\n", "\n\n", s)
    s = s.strip()
    return s


def run_and_save(trend: Optional[str], out_dir: Path, use_mock: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    if use_mock:
        # Provide a canned blog result so you can inspect output without API keys
        mocked_html = (
            "<h1>Mocked AI Report — 300% Growth in Automation Adoption</h1>"
            "<p>Data: automation adoption up 300% among SMBs in 2025. This mock article explains why and how to act.</p>"
            "<h2>Context & Trends</h2><p>Mocked trend data and real examples.</p>"
            "<h2>Main Educational Content</h2><p>Step-by-step mock guidance with examples.</p>"
            "<h2>Reality Check</h2><p>Be honest — mock risks and trade-offs.</p>"
            "<h2>Resources</h2><p>Links and CTAs.</p>"
        )
        result = {
            "blog_html": mocked_html,
            "title": "Mocked AI Report — 300% Growth in Automation Adoption",
            "topic": "ai",
            "intro_paragraph": "Mock excerpt: automation adoption up 300%.",
            "image_url": None,
        }
    else:
        # Call the real generator
        result = generate_blog_content(trend or SAMPLE_TREND, image_path=None)

    if result.get("error"):
        raise RuntimeError(f"Blog generation failed: {result['error']}")

    html_out = result["blog_html"]
    md_out = html_to_markdown_like(html_out)

    # Save files
    html_path = out_dir / "blog_output.html"
    md_path = out_dir / "blog_output.md"

    html_path.write_text(html_out, encoding="utf-8")
    md_path.write_text(md_out, encoding="utf-8")

    return {"html": str(html_path), "md": str(md_path), "result": result}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="./tmp", help="Directory to save output files")
    p.add_argument("--trend", default=None, help="Optional trend data to pass to generator")
    p.add_argument("--mock", action="store_true", help="Use canned mock output (no API keys required)")
    p.add_argument("--format", default="html,md", help="Comma-separated formats to write (html,md)")
    args = p.parse_args()

    out_dir = Path(args.out_dir)

    try:
        saved = run_and_save(args.trend, out_dir, use_mock=args.mock)
        print("Saved blog HTML:", saved["html"])
        print("Saved blog text/MD:", saved["md"])
        print("Title: ", saved["result"].get("title"))
    except Exception as e:
        print("Failed to generate/save blog:", e)
        raise


if __name__ == "__main__":
    main()
