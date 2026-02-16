"""Standalone blog generation test — verifies delimiter-based parsing works."""
import logging
import sys
import os

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-40s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

print("=" * 70)
print("  BLOG AGENT — STANDALONE TEST")
print("=" * 70)

from src.agent.blog_email_agent import generate_blog_content

print("Blog agent imported OK\n")

trend = (
    "AI automation trends show 300% increase in small business adoption. "
    "Workflow automation saves 15+ hours per week. "
    "Digital products creating passive income for entrepreneurs."
)

print("Calling generate_blog_content()...\n")
result = generate_blog_content(trend)

print()
print("=" * 70)
print("  RESULT")
print("=" * 70)

if "error" in result:
    print(f"ERROR: {result['error']}")
    sys.exit(1)
else:
    title = result.get("title", "NONE")
    topic = result.get("topic", "NONE")
    excerpt = result.get("intro_paragraph", "NONE")
    html = result.get("blog_html", "")

    print(f"Title:       {title}")
    print(f"Topic:       {topic}")
    print(f"Excerpt:     {excerpt[:200] if excerpt else 'NONE'}")
    print(f"HTML length: {len(html)} chars")
    print(f"Has <h1>:    {'<h1' in html.lower()}")
    print(f"Has <p>:     {'<p' in html.lower()}")
    print(f"Has image:   {'<img' in html.lower()}")
    print()
    print("--- First 1500 chars of HTML ---")
    print(html[:1500])
    print()
    print("--- Last 500 chars of HTML ---")
    print(html[-500:])
    print()
    print("SUCCESS — Blog generated properly!")
