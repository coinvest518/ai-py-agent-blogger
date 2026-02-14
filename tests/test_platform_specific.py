#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test to verify platform-specific content generation.
Shows each step of the workflow and validates platform-specific posts.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.graph import graph

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str = ""):
    """Print a visual separator"""
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)
    print()


async def test_full_flow_detailed():
    """Run the complete agent flow with detailed output for each step."""
    
    print_separator("🚀 FDWA AI AGENT - FULL WORKFLOW TEST")
    print("Testing: Main Supervisor → Sub-Agents → Platform-Specific Posts")
    print("Expected: Each platform should have unique, tailored content\n")
    
    # Start the workflow
    logger.info("Starting autonomous AI agent workflow...")
    inputs = {}
    
    try:
        # Run the graph
        result = await graph.ainvoke(inputs)
        
        # Display detailed results for each step
        print_separator("📊 WORKFLOW EXECUTION RESULTS")
        
        # Step 1: Research
        print("1️⃣  RESEARCH TRENDS NODE")
        print(f"   Trend Data Length: {len(result.get('trend_data', ''))} characters")
        print(f"   Topic Researched: {result.get('trend_data', 'N/A')[:100]}...")
        print()
        
        # Step 2: Content Generation - Platform-Specific
        print("2️⃣  GENERATE PLATFORM-SPECIFIC CONTENT NODE")
        print()
        
        # Twitter
        twitter_content = result.get('tweet_text', '')
        print("   📱 TWITTER:")
        print(f"      Length: {len(twitter_content)} chars (max 280)")
        print(f"      Content: {twitter_content[:150]}...")
        print()
        
        # Facebook
        facebook_content = result.get('facebook_text', '')
        print("   📘 FACEBOOK:")
        print(f"      Length: {len(facebook_content)} chars (500+ recommended)")
        print(f"      Content: {facebook_content[:150]}...")
        print()
        
        # LinkedIn
        linkedin_content = result.get('linkedin_text', '')
        print("   💼 LINKEDIN:")
        print(f"      Length: {len(linkedin_content)} chars")
        print(f"      Content: {linkedin_content[:150]}...")
        print()
        
        # Instagram
        instagram_content = result.get('instagram_caption', '')
        print("   📸 INSTAGRAM:")
        print(f"      Length: {len(instagram_content)} chars")
        print(f"      Content: {instagram_content[:150]}...")
        print()
        
        # Telegram
        telegram_content = result.get('telegram_message', '')
        print("   ✈️  TELEGRAM:")
        print(f"      Length: {len(telegram_content)} chars")
        print(f"      Content: {telegram_content[:150]}...")
        print()
        
        # Step 3: Image Generation
        print("3️⃣  GENERATE IMAGE NODE")
        print(f"   Image URL: {result.get('image_url', 'N/A')}")
        print()
        
        # Step 4: Twitter
        print("4️⃣  POST TO TWITTER")
        print(f"   Status: {result.get('twitter_url', 'N/A')}")
        print()
        
        # Step 5: Facebook
        print("5️⃣  POST TO FACEBOOK")
        print(f"   Status: {result.get('facebook_status', 'N/A')}")
        print()
        
        # Step 6: LinkedIn
        print("6️⃣  POST TO LINKEDIN")
        print(f"   Status: {result.get('linkedin_status', 'N/A')}")
        print()
        
        # Step 7: Telegram
        print("7️⃣  POST TO TELEGRAM")
        print(f"   Status: {result.get('telegram_status', 'N/A')}")
        print()
        
        # Step 8: Instagram
        print("8️⃣  POST TO INSTAGRAM")
        print(f"   Status: {result.get('instagram_status', 'N/A')}")
        print()
        
        # Step 9: Monitor Instagram Comments
        print("9️⃣  MONITOR INSTAGRAM COMMENTS")
        print(f"   Status: {result.get('instagram_comment_status', 'N/A')}")
        print()
        
        # Step 10: Reply to Twitter
        print("🔟 REPLY TO TWITTER")
        print(f"   Status: {result.get('twitter_reply_status', 'N/A')}")
        print()
        
        # Step 11: Comment on Facebook
        print("1️⃣1️⃣ COMMENT ON FACEBOOK")
        print(f"   Status: {result.get('comment_status', 'N/A')}")
        print()
        
        # Step 12: Generate Blog Email
        print("1️⃣2️⃣ GENERATE BLOG EMAIL")
        print(f"   Status: {result.get('blog_status', 'N/A')}")
        print(f"   Blog Title: {result.get('blog_title', 'N/A')}")
        print()
        
        # Analysis
        print_separator("🔍 ANALYSIS: Platform-Specific Content Validation")
        
        # Get all platform content
        twitter_content = result.get('tweet_text', '')
        facebook_content = result.get('facebook_text', '')
        linkedin_content = result.get('linkedin_text', '')
        instagram_content = result.get('instagram_caption', '')
        telegram_content = result.get('telegram_message', '')
        
        # Check uniqueness
        contents = {
            'Twitter': twitter_content,
            'Facebook': facebook_content,
            'LinkedIn': linkedin_content,
            'Instagram': instagram_content,
            'Telegram': telegram_content
        }
        
        # Remove empty contents
        non_empty_contents = {k: v for k, v in contents.items() if v}
        
        print(f"📊 Generated Content for {len(non_empty_contents)} platforms:")
        print()
        
        # Check if all content is unique
        unique_contents = set(non_empty_contents.values())
        
        if len(unique_contents) == len(non_empty_contents):
            print("✅ SUCCESS: All platforms have UNIQUE content!")
            print()
            for platform, content in non_empty_contents.items():
                print(f"   {platform}:")
                print(f"      Length: {len(content)} chars")
                print(f"      First 80 chars: {content[:80]}...")
                print()
        else:
            print("❌ WARNING: Some platforms have DUPLICATE content!")
            print()
            # Find duplicates
            seen = {}
            for platform, content in non_empty_contents.items():
                if content in seen:
                    print(f"   ⚠️  {platform} has same content as {seen[content]}")
                else:
                    seen[content] = platform
            print()
        
        # Platform-specific validation
        print("🎯 Platform Format Validation:")
        print()
        
        if twitter_content:
            twitter_ok = len(twitter_content) <= 280 and '#' in twitter_content
            print(f"   Twitter: {'✅' if twitter_ok else '❌'} (<= 280 chars, has hashtags)")
            print(f"      Actual: {len(twitter_content)} chars, {'hashtags present' if '#' in twitter_content else 'NO hashtags'}")
        
        if facebook_content:
            facebook_ok = len(facebook_content) > 300
            print(f"   Facebook: {'✅' if facebook_ok else '❌'} (> 300 chars for engagement)")
            print(f"      Actual: {len(facebook_content)} chars")
        
        if linkedin_content:
            linkedin_ok = 'www.fdwa.site' in linkedin_content or 'fdwa' in linkedin_content.lower()
            print(f"   LinkedIn: {'✅' if linkedin_ok else '❌'} (includes FDWA link/mention)")
            print(f"      Actual: {'FDWA mentioned' if linkedin_ok else 'NO FDWA mention'}")
        
        if instagram_content:
            instagram_ok = '✨' in instagram_content or '🚀' in instagram_content or '💡' in instagram_content
            print(f"   Instagram: {'✅' if instagram_ok else '❌'} (has visual emojis)")
            print(f"      Actual: {'Emojis present' if instagram_ok else 'NO emojis'}")
        
        if telegram_content:
            telegram_ok = 'fdwa.site' in telegram_content.lower()
            print(f"   Telegram: {'✅' if telegram_ok else '❌'} (includes direct link/CTA)")
            print(f"      Actual: {'Link present' if telegram_ok else 'NO link'}")
        print()
        
        # Architecture Status
        print_separator("✅ CURRENT ARCHITECTURE")
        print("research_trends → generate_platform_specific_content →")
        print("  ├─ tweet_text (Twitter: 280 chars, hashtags)")
        print("  ├─ facebook_text (Facebook: 500+ chars, conversational)")
        print("  ├─ linkedin_text (LinkedIn: professional, business-focused)")
        print("  ├─ instagram_caption (Instagram: visual, emoji-heavy)")
        print("  └─ telegram_message (Telegram: direct CTA, action-oriented)")
        print()
        print("Each platform node uses its specific content field from state.")
        print()
        
        if result.get("error"):
            print(f"⚠️  Error encountered: {result.get('error')}")
        
        print_separator("✅ TEST COMPLETE")
        
        return result
        
    except Exception as e:
        logger.exception("Agent execution failed")
        print(f"\n❌ ERROR: {e}\n")
        return None


if __name__ == "__main__":
    print("Running platform-specific content validation test...")
    print("This validates that each platform receives unique, optimized content.\n")
    
    result = asyncio.run(test_full_flow_detailed())
    
    if result:
        print("\n✅ Test completed! Review the platform-specific content above.")
    else:
        print("\n❌ Test failed!")