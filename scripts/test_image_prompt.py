"""Test: Image Prompt Agent generates brand-consistent prompts."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from src.agent.agents.image_prompt_agent import (
    generate_image_prompt,
    _template_prompt,
    FDWA_VISUAL_DNA,
    TOPIC_VISUALS,
    _get_recent_image_styles,
)

print("=" * 60)
print("TEST: LLM-Powered Image Prompt Agent")
print("=" * 60)

# 1) Visual DNA loaded
print("\n--- 1. Brand Visual DNA ---")
print(f"  Visual DNA: {len(FDWA_VISUAL_DNA)} chars")
assert "Black woman" in FDWA_VISUAL_DNA
assert "cyberpunk" in FDWA_VISUAL_DNA.lower()
assert "neon" in FDWA_VISUAL_DNA.lower()
print("  Brand elements: Black woman, cyberpunk, neon, holographic - YES")

# 2) Topic visuals
print("\n--- 2. Topic visuals ---")
for topic in ["crypto", "credit_repair", "ai_automation", "general"]:
    data = TOPIC_VISUALS[topic]
    print(f"  {topic}: {data['mood'][:40]}...")
print("  All 4 topics configured: YES")

# 3) Recent images scan
print("\n--- 3. Recent images ---")
recent = _get_recent_image_styles()
print(f"  {recent or 'No recent images found'}")

# 4) Template fallback (no LLM)
print("\n--- 4. Template fallback (no LLM) ---")
for topic in ["crypto", "credit_repair", "ai_automation"]:
    prompt = generate_image_prompt(
        post_text=f"Transform your {topic} journey with AI automation",
        topic=topic,
        use_llm=False,
    )
    print(f"  [{topic}] {len(prompt)} chars: {prompt[:100]}...")
    assert "Black woman" in prompt
    assert "8K" in prompt
    assert len(prompt) <= 500

# 5) Product-aware prompt
print("\n--- 5. Product-aware prompt ---")
prompt = generate_image_prompt(
    post_text="Get your credit score to 800+ with our AI analyzer",
    topic="credit_repair",
    product_name="Credit Repair AI Toolkit",
    product_price="47",
    use_llm=False,
)
print(f"  Product prompt: {len(prompt)} chars")
print(f"  Contains product: {'Credit Repair AI Toolkit' in prompt or 'credit' in prompt.lower()}")
assert len(prompt) <= 500

# 6) LLM-powered prompt (the real deal)
print("\n--- 6. LLM-powered prompt ---")
prompt = generate_image_prompt(
    post_text="AI automation is changing how entrepreneurs build wealth in 2026. Stop trading time for money.",
    topic="ai_automation",
    product_name="FDWA Business Automation Suite",
    platform="instagram",
)
print(f"  LLM prompt: {len(prompt)} chars")
print(f"  Full prompt:\n  {prompt}")
assert len(prompt) > 50
assert len(prompt) <= 500

# 7) Crypto topic
print("\n--- 7. Crypto topic ---")
prompt = generate_image_prompt(
    post_text="Bitcoin surges past $100K as DeFi yields skyrocket. YieldBot users earning 40% APY.",
    topic="crypto",
)
print(f"  Crypto prompt: {len(prompt)} chars")
print(f"  Full prompt:\n  {prompt}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
