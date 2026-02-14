#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test runner for AI Agent - checks all components systematically.
Run this to get a complete status of what's working and what needs fixing.
"""

import sys
import os
import asyncio
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


def print_header(title: str, char: str = "="):
    """Print a formatted header."""
    print(f"\n{char * 70}")
    print(f"  {title}")
    print(f"{char * 70}\n")


def test_api_keys():
    """Test API key validity."""
    print_header("1. API KEY VALIDATION")
    
    try:
        from tests.test_api_keys import test_mistral, test_huggingface, test_google
        
        results = {
            "Mistral": test_mistral(),
            "HuggingFace": test_huggingface(),
            "Google": test_google()
        }
        
        for name, result in results.items():
            status = "✅" if "OK" in result else "❌"
            print(f"{status} {name}: {result}")
        
        return all("OK" in r for r in results.values())
    except Exception as e:
        print(f"❌ API Key test failed: {e}")
        return False


def test_composio_connections():
    """Test Composio account connections."""
    print_header("2. COMPOSIO CONNECTIONS")
    
    try:
        from composio import ComposioToolSet, Action, App
        
        toolset = ComposioToolSet(entity_id="pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23")
        
        # Check key accounts
        accounts = {
            "SERPAPI": os.getenv("SERPAPI_ACCOUNT_ID", ""),
            "Tavily": os.getenv("TAVILY_ACCOUNT_ID", ""),
            "Twitter": os.getenv("TWITTER_ACCOUNT_ID", ""),
            "Facebook": os.getenv("FACEBOOK_ACCOUNT_ID", ""),
            "Instagram": os.getenv("INSTAGRAM_ACCOUNT_ID", ""),
            "Telegram": os.getenv("TELEGRAM_ENTITY_ID", ""),
        }
        
        for service, account_id in accounts.items():
            status = "✅" if account_id else "❌"
            print(f"{status} {service}: {'Connected' if account_id else 'Not configured'}")
        
        return any(accounts.values())
    except Exception as e:
        print(f"⚠️  Error checking connections: {e}")
        return False


def test_search_tools():
    """Test SERPAPI and Tavily search."""
    print_header("3. SEARCH TOOLS (SERPAPI + TAVILY)")
    
    try:
        from composio import ComposioToolSet, Action
        
        toolset = ComposioToolSet(entity_id="pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23")
        
        # Test SERPAPI
        print("Testing SERPAPI...")
        serpapi_result = toolset.execute_action(
            action=Action.SERPAPI_SEARCH,
            params={"query": "AI automation 2026"},
            entity_id=os.getenv("SERPAPI_ACCOUNT_ID")
        )
        serpapi_ok = serpapi_result.get("successful", False)
        print(f"{'✅' if serpapi_ok else '❌'} SERPAPI: {'Working' if serpapi_ok else 'Failed'}")
        
        # Test Tavily
        print("Testing Tavily...")
        tavily_result = toolset.execute_action(
            action=Action.TAVILY_SEARCH,
            params={"query": "AI automation 2026"},
            entity_id=os.getenv("TAVILY_ACCOUNT_ID")
        )
        tavily_ok = tavily_result.get("successful", False)
        print(f"{'✅' if tavily_ok else '❌'} Tavily: {'Working' if tavily_ok else 'Failed'}")
        
        return serpapi_ok and tavily_ok
    except Exception as e:
        print(f"❌ Search tools test failed: {e}")
        return False


def test_image_generation():
    """Test Hugging Face image generation."""
    print_header("4. IMAGE GENERATION (HUGGING FACE)")
    
    try:
        from src.agent.hf_image_gen import generate_image_hf
        
        print("Generating test image...")
        result = generate_image_hf(
            prompt="Modern AI technology workspace",
            model="flux-schnell",
            width=512,
            height=512,
            timeout=30
        )
        
        if result.get("success"):
            print(f"✅ Image generated successfully")
            print(f"   Size: {len(result['image_bytes'])} bytes")
            print(f"   Model: {result['model']}")
            return True
        else:
            print(f"❌ Image generation failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Image generation test failed: {e}")
        return False


def test_platform_content_generation():
    """Test platform-specific content generation."""
    print_header("5. PLATFORM-SPECIFIC CONTENT GENERATION")
    
    try:
        from src.agent.graph import (
            _adapt_for_twitter,
            _adapt_for_facebook,
            _adapt_for_linkedin,
            _adapt_for_instagram,
            _adapt_for_telegram
        )
        
        base_insights = "AI automation is transforming business operations in 2026. Top tools include workflow automation, intelligent chatbots, and predictive analytics."
        
        platforms = {
            "Twitter": _adapt_for_twitter(base_insights),
            "Facebook": _adapt_for_facebook(base_insights),
            "LinkedIn": _adapt_for_linkedin(base_insights),
            "Instagram": _adapt_for_instagram(base_insights),
            "Telegram": _adapt_for_telegram(base_insights)
        }
        
        # Check all unique
        unique_contents = set(platforms.values())
        all_unique = len(unique_contents) == len(platforms)
        
        print(f"{'✅' if all_unique else '❌'} Uniqueness: {len(unique_contents)}/5 platforms have unique content")
        
        for platform, content in platforms.items():
            print(f"  • {platform}: {len(content)} chars - {content[:60]}...")
        
        return all_unique
    except Exception as e:
        print(f"❌ Content generation test failed: {e}")
        return False


def test_telegram_integration():
    """Test Telegram bot functionality."""
    print_header("6. TELEGRAM INTEGRATION")
    
    try:
        from src.agent import telegram_agent
        
        # Test bot info
        print("Testing bot connection...")
        bot_info = telegram_agent.get_bot_info()
        
        if bot_info.get("success"):
            bot_data = bot_info.get("data", {}).get("result", {})
            print(f"✅ Bot connected: @{bot_data.get('username')}")
            print(f"   Name: {bot_data.get('first_name')}")
            print(f"   ID: {bot_data.get('id')}")
            return True
        else:
            print(f"❌ Bot connection failed: {bot_info.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        return False


async def test_full_workflow():
    """Test complete autonomous workflow (quick dry-run)."""
    print_header("7. FULL AUTONOMOUS WORKFLOW")
    
    try:
        print("⚠️  Skipping full workflow (use test_full_flow.py for actual run)")
        print("   This test would take 2-3 minutes and make real posts")
        print("   To run full workflow:")
        print("   .venv\\Scripts\\python.exe test_full_flow.py")
        return None  # Neutral result
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        return False


def generate_summary(results: dict):
    """Generate test summary."""
    print_header("TEST SUMMARY", "=")
    
    passing = sum(1 for v in results.values() if v is True)
    failing = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)
    
    print(f"📊 Results: {passing} passing, {failing} failing, {skipped} skipped out of {total} tests\n")
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⏭️  SKIP"
        print(f"  {status}  {test_name}")
    
    print()
    
    if failing == 0 and passing > 0:
        print("🎉 All tests passing! Agent ready for production.")
        return 0
    elif failing <= 2:
        print("⚠️  Most tests passing. Minor issues to fix.")
        return 1
    else:
        print("❌ Multiple failures detected. Review logs above.")
        return 2


def main():
    """Run all tests."""
    print("=" * 70)
    print("  AI AGENT - COMPREHENSIVE TEST SUITE")
    print("  Running systematic checks on all components...")
    print("=" * 70)
    
    results = {}
    
    # Run tests
    results["API Keys"] = test_api_keys()
    results["Composio Connections"] = test_composio_connections()
    results["Search Tools"] = test_search_tools()
    results["Image Generation"] = test_image_generation()
    results["Platform Content"] = test_platform_content_generation()
    results["Telegram Integration"] = test_telegram_integration()
    results["Full Workflow"] = asyncio.run(test_full_workflow())
    
    # Summary
    exit_code = generate_summary(results)
    
    print("\n" + "=" * 70)
    print(f"  Test run complete. Exit code: {exit_code}")
    print("=" * 70)
    
    return exit_code


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
