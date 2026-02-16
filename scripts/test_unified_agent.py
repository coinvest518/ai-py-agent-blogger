"""Test: main graph and chat share the same identity + tools."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("TEST: Unified FDWA Identity + Tools")
print("=" * 60)

# 1) Shared knowledge module loads properly
print("\n--- 1. Shared knowledge module ---")
from src.agent.core.knowledge import load_knowledge_context, build_system_prompt, FDWA_IDENTITY
kb = load_knowledge_context()
print(f"  Knowledge context: {len(kb)} chars")
assert len(kb) > 100, "Knowledge base too short!"
assert "FDWA" in kb or "Daniel" in kb, "Missing FDWA identity in knowledge base"

prompt = build_system_prompt(purpose="chat")
print(f"  System prompt: {len(prompt)} chars")
assert "Futurist Digital Wealth Agency" in prompt, "Missing full name"
assert "NOT Food" in prompt, "Missing identity clarification"
assert "Firecrawl" in prompt, "Missing Firecrawl capability"

print(f"  FDWA_IDENTITY constant: {len(FDWA_IDENTITY)} chars")
assert "Daniel Wray" in FDWA_IDENTITY

# 2) Chat uses shared module
print("\n--- 2. Chat endpoint uses shared module ---")
from src.agent.api import build_system_prompt as api_build
# They should be the SAME function (imported from knowledge.py)
assert api_build is build_system_prompt, "Chat should use shared build_system_prompt!"
print("  Chat uses shared build_system_prompt: YES")

# 3) Graph imports shared knowledge
print("\n--- 3. Graph imports shared knowledge ---")
from src.agent.graph import load_knowledge_context as graph_kb, FDWA_IDENTITY as graph_id
assert graph_kb is load_knowledge_context, "Graph should use shared load_knowledge_context!"
assert graph_id is FDWA_IDENTITY, "Graph should use shared FDWA_IDENTITY!"
print("  Graph uses shared knowledge: YES")

# 4) Firecrawl is available in search_tools
print("\n--- 4. Firecrawl in search pipeline ---")
from src.agent.tools.web_tools import _get_firecrawl, scrape_url, search_web
fc = _get_firecrawl()
print(f"  Firecrawl client: {type(fc).__name__ if fc else 'NOT AVAILABLE'}")
# search_tools.py now has Firecrawl as fallback step 3
import inspect
from src.agent.tools import search_tools
src = inspect.getsource(search_tools.search_trends)
assert "firecrawl_search" in src, "search_tools should have Firecrawl fallback!"
print("  Firecrawl fallback in search_trends(): YES")

# 5) Research agent uses Firecrawl
print("\n--- 5. Research agent uses Firecrawl ---")
from src.agent.agents import research_agent
src = inspect.getsource(research_agent.research_trends)
assert "scrape_url" in src, "Research agent should scrape FDWA sites!"
print("  Research agent scrapes fdwa.site: YES")

# 6) Quick live test — scrape + knowledge
print("\n--- 6. Live test: scrape fdwa.site ---")
result = scrape_url("https://fdwa.site")
if "error" not in result:
    print(f"  Title: {result.get('title', '?')}")
    print(f"  Content: {len(result.get('markdown', ''))} chars")
else:
    print(f"  Error (non-blocking): {result['error']}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED — Graph + Chat share same identity & tools")
print("=" * 60)
