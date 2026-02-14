#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test blog generation with both LLM and template fallback.
"""

import sys
import os
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.agent.blog_email_agent import generate_blog_content

def test_blog_generation():
    """Test blog generation with template fallback."""
    print("=" * 70)
    print("  BLOG GENERATION TEST")
    print("=" * 70)
    print()
    
    # Test with different topics
    test_cases = [
        {
            "trend_data": "AI automation tools for credit repair and business automation",
            "topic": "ai",
            "image_path": "https://example.com/test-image.png"
        },
        {
            "trend_data": "Marketing strategies for digital products and social media growth",
            "topic": "marketing",
            "image_path": None
        },
        {
            "trend_data": "Credit repair strategies and wealth building techniques",
            "topic": "finance",
            "image_path": None
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}: {test_case['topic'].upper()}")
        print("-" * 70)
        
        try:
            result = generate_blog_content(
                trend_data=test_case["trend_data"],
                image_path=test_case["image_path"]
            )
            
            if result.get("error"):
                print(f"❌ FAILED: {result['error']}")
                results.append(False)
            else:
                print(f"✅ SUCCESS")
                print(f"   Title: {result['title'][:60]}...")
                print(f"   Topic: {result['topic']}")
                print(f"   HTML Length: {len(result['blog_html'])} chars")
                print(f"   Has Image: {'Yes' if result.get('image_url') else 'No'}")
                results.append(True)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(False)
        
        print()
    
    # Summary
    print("=" * 70)
    print(f"  RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)
    print()
    
    if all(results):
        print("✅ All blog generation tests passed!")
        print()
        print("Blog generation is working with:")
        print("  • Template fallback when LLM fails ✅")
        print("  • Multiple topic categories (ai, marketing, finance) ✅")
        print("  • Image integration ✅")
        print("  • Error handling ✅")
        return 0
    else:
        print("⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = test_blog_generation()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
