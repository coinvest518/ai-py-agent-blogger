"""🧪 COMPREHENSIVE FULL WORKFLOW TEST

This test simulates the COMPLETE agent workflow step-by-step to identify issues:
1. LLM Provider Check (which LLMs are available?)
2. Trend Research (can we get topics?)
3. Content Generation (does LLM work for tweets?)
4. Image Generation (Pollinations → HF fallback)
5. ImgBB Upload (can we get public URLs?)
6. Memory Recording (does long-term memory save?)

Run this to diagnose what's working and what's broken.
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

def test_header(title):
    """Print test section header"""
    print("\n" + "="*80)
    print(f"🧪 TEST: {title}")
    print("="*80)

def test_result(success, message):
    """Print test result"""
    icon = "✅" if success else "❌"
    status = "PASS" if success else "FAIL"
    print(f"{icon} {status}: {message}")
    return success

# ============================================================================
# TEST 1: Environment Variables & API Keys
# ============================================================================
def test_environment():
    test_header("Environment Variables & API Keys")
    
    results = {
        "MISTRAL_API_KEY": bool(os.getenv("MISTRAL_API_KEY")),
        "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
        "APIFREELLM_API_KEY": bool(os.getenv("APIFREELLM_API_KEY")),
        "HF_TOKEN": bool(os.getenv("HF_TOKEN")),
        "POLLINATIONS_API_KEY": bool(os.getenv("POLLINATIONS_API_KEY")),
        "FREEPIK_API_KEY": bool(os.getenv("FREEPIK_API_KEY")),
        "IMGBB_API_KEY": bool(os.getenv("IMGBB_API_KEY")),
        "COMPOSIO_API_KEY": bool(os.getenv("COMPOSIO_API_KEY")),
        "SERPAPI_ACCOUNT_ID": bool(os.getenv("SERPAPI_ACCOUNT_ID")),  # Using SERPAPI through Composio
    }
    
    # Check HF_ENABLE separately (shows enabled/disabled, not just set/not set)
    hf_enabled = os.getenv("HF_ENABLE", "false").lower() in ("1", "true", "yes")
    results["HF_ENABLE"] = hf_enabled
    
    for key, value in results.items():
        if key == "HF_ENABLE":
            status = "ENABLED" if value else "DISABLED (Pollinations only)"
            test_result(True, f"{key} = {status}")  # Always pass - it's a config choice
        else:
            test_result(value, f"{key} = {'SET' if value else 'NOT SET'}")
    
    # Count available LLMs
    llm_count = sum([
        results["MISTRAL_API_KEY"],
        results["OPENROUTER_API_KEY"],
        results["APIFREELLM_API_KEY"]
    ])
    
    # Count image generation providers
    image_providers = []
    if results["POLLINATIONS_API_KEY"]:
        image_providers.append("Pollinations")
    if results["FREEPIK_API_KEY"]:
        image_providers.append("Freepik ($0.005/img)")
    if hf_enabled:
        image_providers.append("HuggingFace")
    
    print(f"\n📊 Available LLMs: {llm_count}/3")
    print(f"🖼️  Image Generation: {' → '.join(image_providers) if image_providers else 'None configured!'}")
    print(f"    Cascade: {'3-tier fallback ready' if len(image_providers) >= 2 else 'Single provider only'}")
    print(f"🔍 Search: {'Composio SERPAPI' if results['SERPAPI_ACCOUNT_ID'] else 'No search configured'}")
    
    return llm_count > 0

# ============================================================================
# TEST 2: LLM Provider Cascade
# ============================================================================
def test_llm_providers():
    test_header("LLM Provider Cascade (Mistral → OpenRouter → APIFreeLLM)")
    
    try:
        from src.agent.llm_provider import get_llm
        
        # Test simple prompt
        llm = get_llm(purpose="test")
        response = llm.invoke("Say only: TEST OK")
        content = response.content if hasattr(response, 'content') else str(response)
        
        return test_result(True, f"LLM responded: {content[:50]}")
    except Exception as e:
        return test_result(False, f"LLM failed: {e}")

# ============================================================================
# TEST 3: Trend Research (SERPAPI)
# ============================================================================
def test_trend_research():
    test_header("Trend Research (SERPAPI)")
    
    try:
        from src.agent.graph import research_trends_node
        
        # Simulate initial state
        state = {
            "topic": None,
            "trends": None
        }
        
        result = research_trends_node(state)
        
        # Fix: Check for trend_data (correct field name) instead of trends
        if result.get("trend_data") and len(result["trend_data"]) > 20:
            trend_data = result["trend_data"]
            test_result(True, f"Found trends: {len(trend_data)} characters")
            print(f"   Sample: {trend_data[:100]}...")
            return True
        else:
            error_msg = result.get("error", "No trend data extracted")
            return test_result(False, f"No trends found: {error_msg}")
    except Exception as e:
        return test_result(False, f"Trend research failed: {e}")

# ============================================================================
# TEST 4: Content Generation (AI Decision Engine)
# ============================================================================
def test_content_generation():
    test_header("Content Generation (AI Decision Engine + LLM)")
    
    try:
        from src.agent.graph import generate_tweet_node
        
        # Simulate state with trends
        state = {
            "trends": ["AI automation is revolutionizing business"],
            "topic": "AI automation",
            "tweet_text": None,
            "facebook_post": None,
            "linkedin_post": None
        }
        
        result = generate_tweet_node(state)
        
        tweet = result.get("tweet_text")
        if tweet:
            test_result(True, f"Generated tweet ({len(tweet)} chars)")
            print(f"   Tweet: {tweet}")
            
            # Check other platforms with CORRECT field names
            test_result(bool(result.get("facebook_text")), "Facebook post generated")
            test_result(bool(result.get("linkedin_text")), "LinkedIn post generated")
            test_result(bool(state.get("ai_strategy")), "AI Strategy used")  # ai_strategy is in state, not result
            
            return True
        else:
            return test_result(False, "No tweet generated")
    except Exception as e:
        return test_result(False, f"Content generation failed: {e}")

# ============================================================================
# TEST 5: Image Generation (3-Tier: Pollinations → Freepik → HF)
# ============================================================================
def test_image_generation():
    test_header("Image Generation (Pollinations → Freepik → HuggingFace)")
    
    try:
        from src.agent.pollinations_image_gen import generate_image_with_fallback
        
        prompt = "Professional business AI automation technology, modern design, blue and green colors"
        
        print(f"🎨 Prompt: {prompt}")
        result = generate_image_with_fallback(
            prompt=prompt,
            width=512,  # Smaller for faster testing
            height=512,
            timeout=60
        )
        
        if result.get("success"):
            provider = result.get("provider", "Unknown")
            size = len(result.get("image_bytes", b""))
            test_result(True, f"Image generated with {provider} ({size} bytes)")
            return result
        else:
            error = result.get("error", "Unknown error")
            test_result(False, f"Image generation failed: {error}")
            return None
    except Exception as e:
        test_result(False, f"Image generation crashed: {e}")
        return None

# ============================================================================
# TEST 6: ImgBB Upload
# ============================================================================
def test_imgbb_upload(image_result):
    test_header("ImgBB Upload (Public URL Hosting)")
    
    if not image_result or not image_result.get("success"):
        return test_result(False, "Skipped - no image to upload")
    
    try:
        from src.agent.pollinations_image_gen import upload_to_imgbb
        
        image_bytes = image_result.get("image_bytes")
        if not image_bytes:
            return test_result(False, "No image bytes to upload")
        
        upload_result = upload_to_imgbb(image_bytes)
        
        if upload_result.get("success"):
            url = upload_result.get("url")
            test_result(True, f"Image uploaded to: {url}")
            return True
        else:
            error = upload_result.get("error")
            return test_result(False, f"Upload failed: {error}")
    except Exception as e:
        return test_result(False, f"Upload crashed: {e}")

# ============================================================================
# TEST 7: Memory System
# ============================================================================
def test_memory_system():
    test_header("Long-Term Memory System")
    
    try:
        from src.agent.memory_store import get_memory_store
        
        memory = get_memory_store(user_id="test_user")
        
        # Test 1: Save content performance
        memory.record_post_performance(
            topic="test_topic",
            platform="twitter",
            engagement=100,
            success=True,
            metadata={"test": True}
        )
        test_result(True, "Saved post performance")
        
        # Test 2: Retrieve successful topics
        topics = memory.get_successful_topics(limit=1)
        test_result(len(topics) > 0, f"Retrieved {len(topics)} successful topics")
        
        # Test 3: Save product mention
        memory.record_product_mention(
            product_name="Test Product",
            platform="twitter",
            engagement=50,
            conversion=False
        )
        test_result(True, "Saved product mention")
        
        # Test 4: Save crypto insight
        memory.record_crypto_insight(
            token_symbol="BTC",
            insight_type="test",
            data={"price": 50000}
        )
        test_result(True, "Saved crypto insight")
        
        return True
    except Exception as e:
        return test_result(False, f"Memory system failed: {e}")

# ============================================================================
# TEST 8: AI Decision Engine
# ============================================================================
def test_ai_decision_engine():
    test_header("AI Decision Engine (Smart Content Selection)")
    
    try:
        from src.agent.ai_decision_engine import get_decision_engine
        
        engine = get_decision_engine()
        
        # Test strategy generation with correct parameter
        trend_text = "AI automation and business growth are trending topics in 2026"
        strategy = engine.get_content_strategy(trend_data=trend_text)
        
        if strategy:
            test_result(True, f"Generated strategy for topic: {strategy.get('topic')}")
            print(f"   Products: {len(strategy.get('products', []))} selected")
            print(f"   CTA: {strategy.get('cta', 'N/A')[:50]}")
            return True
        else:
            return test_result(False, "No strategy generated")
    except Exception as e:
        return test_result(False, f"AI Decision Engine failed: {e}")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def main():
    print("\n" + "🚀 FDWA AGENT COMPREHENSIVE WORKFLOW TEST")
    print("="*80)
    print("Testing ALL components of the agent workflow...")
    print("="*80)
    
    results = []
    
    # Run all tests
    results.append(("Environment Setup", test_environment()))
    results.append(("LLM Providers", test_llm_providers()))
    results.append(("AI Decision Engine", test_ai_decision_engine()))
    results.append(("Trend Research", test_trend_research()))
    results.append(("Content Generation", test_content_generation()))
    
    image_result = test_image_generation()
    results.append(("Image Generation", image_result is not None))
    results.append(("ImgBB Upload", test_imgbb_upload(image_result)))
    results.append(("Memory System", test_memory_system()))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed = sum(1 for _, success in results if success)
    failed = total_tests - passed
    
    for test_name, success in results:
        icon = "✅" if success else "❌"
        print(f"{icon} {test_name}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total_tests} tests passed ({failed} failed)")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! Agent is fully operational.")
    else:
        print(f"⚠️  {failed} test(s) failed. Check logs above for details.")
    
    print("="*80 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"💥 Test suite crashed: {e}")
        sys.exit(1)
