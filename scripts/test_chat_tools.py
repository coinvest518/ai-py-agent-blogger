"""Quick test for Firecrawl integration + chat system context."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

# Test 1: Firecrawl client init
print("=== Test 1: Firecrawl client init ===")
from src.agent.tools.web_tools import _get_firecrawl, scrape_url, search_web, extract_urls
fc = _get_firecrawl()
fc_type = type(fc).__name__ if fc else "NONE"
print(f"Firecrawl client: {fc_type}")
assert fc is not None, "Firecrawl client failed to init — check FIRECRAWL_API_KEY"

# Test 2: URL extraction
print("\n=== Test 2: URL extraction ===")
urls = extract_urls("Check this out https://fdwa.site and also https://yieldbot.cc ok?")
print(f"Found URLs: {urls}")
assert len(urls) == 2

# Test 3: Quick scrape test
print("\n=== Test 3: Scrape fdwa.site ===")
result = scrape_url("https://fdwa.site")
if "error" in result:
    print(f"Error: {result['error']}")
else:
    title = result.get("title", "?")
    md = result.get("markdown", "")
    print(f"Title: {title}")
    print(f"Content length: {len(md)} chars")
    print(f"First 300 chars:\n{md[:300]}")

# Test 4: System context loading
print("\n=== Test 4: Chat system context ===")
# Import after dotenv
from src.agent.api import _load_system_context, _build_system_prompt
ctx = _load_system_context()
print(f"System context loaded: {len(ctx)} chars")
assert "FDWA" in ctx or "Daniel" in ctx, "Knowledge base not loaded!"

prompt = _build_system_prompt()
print(f"Full system prompt: {len(prompt)} chars")
assert "Futurist Digital Wealth Agency" in prompt
assert "NOT Food" in prompt

print("\n=== ALL TESTS PASSED ===")
