"""Generate a blog post using the real LLM chain and save HTML + markdown.

Usage examples:
  python scripts/generate_blog_real.py --require-llm --out-dir=temp_blog_output
  python scripts/generate_blog_real.py --trend "AI automation trends..." --out-dir=out

This script does NOT mock any LLM — it calls `generate_blog_content` directly and will
fail if no LLM provider is available and `--require-llm` is passed.
"""
import argparse
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup
import sys
# ensure ai-agent src/ package is importable when running the script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.agent.blog_email_agent import generate_blog_content


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:100] or "blog-post"


def html_to_plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # preserve paragraph breaks
    return soup.get_text("\n\n").strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trend", default=(
        "AI automation trends show 300% increase in small business adoption. "
        "Workflow automation saves 15+ hours per week for entrepreneurs."), help="Trend data to feed the LLM")
    p.add_argument("--image", default=None, help="Optional image URL to embed in the blog")
    p.add_argument("--out-dir", default="temp_blog_output", help="Directory to save the generated files")
    p.add_argument("--require-llm", action="store_true", help="Fail if no LLM provider is available (no template fallback)")
    args = p.parse_args()

    if args.require_llm:
        os.environ["BLOG_REQUIRE_LLM"] = "true"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generating blog (LLM-only mode: %s)" % ("YES" if args.require_llm else "no"))

    result = generate_blog_content(trend_data=args.trend, image_path=args.image)

    if "error" in result:
        print("ERROR from generator:", result["error"])
        return 2

    title = result.get("title", "blog-post")
    blog_html = result.get("blog_html", "")
    excerpt = result.get("intro_paragraph", "")
    topic = result.get("topic", "")

    filename = slugify(title)
    html_path = out_dir / f"{filename}.html"
    md_path = out_dir / f"{filename}.md"

    # Save HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(blog_html)

    # Save markdown-like text (title + excerpt + plain text body)
    plain = html_to_plain_text(blog_html)
    md_contents = f"# {title}\n\n" + (f"{excerpt}\n\n" if excerpt else "") + f"**Topic**: {topic}\n\n" + plain
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_contents)

    print(f"Saved HTML: {html_path}")
    print(f"Saved MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
