#!/usr/bin/env python3
"""
TEST FULL AI AGENT FLOW
========================
This runs the complete autonomous agent workflow to see what the AI creates and posts.
"""
import json
from datetime import datetime

from src.agent.graph import graph

print("=" * 70)
print("🤖 TESTING FULL AI AGENT WORKFLOW")
print("=" * 70)
print(f"\n⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("\n📋 Workflow Steps:")
print("   1. Research trending topics")
print("   2. Generate strategic tweet with FDWA context")
print("   3. Check for duplicates")
print("   4. Post to Twitter")
print("   5. Adapt and post to Facebook")
print("   6. Post to Telegram (with crypto data)")
print("   7. Post to Instagram")
print("   8. Monitor Instagram comments")
print("   9. Generate and send blog email")
print("\n⚙️  Starting agent...\n")

try:
    # Run the complete workflow
    result = graph.invoke({})
    
    print("\n" + "=" * 70)
    print("✅ AGENT EXECUTION COMPLETE!")
    print("=" * 70)
    
    # Display results
    print(f"\n🐦 TWITTER:")
    print(f"   Tweet: {result.get('tweet_text', 'N/A')[:250]}...")
    print(f"   URL: {result.get('twitter_url', 'N/A')}")
    print(f"   Image: {result.get('image_url', 'N/A')}")
    
    print(f"\n📘 FACEBOOK:")
    print(f"   Status: {result.get('facebook_status', 'N/A')}")
    
    print(f"\n💬 TELEGRAM:")
    print(f"   Status: {result.get('telegram_status', 'N/A')}")
    print(f"   Message: {result.get('telegram_message', 'N/A')[:150]}...")
    
    print(f"\n📸 INSTAGRAM:")
    print(f"   Status: {result.get('instagram_status', 'N/A')}")
    
    print(f"\n💼 LINKEDIN:")
    print(f"   Status: {result.get('linkedin_status', 'N/A')}")
    
    print(f"\n📧 BLOG/EMAIL:")
    print(f"   Title: {result.get('blog_title', 'N/A')}")
    print(f"   Status: {result.get('blog_status', 'N/A')}")
    
    if result.get('error'):
        print(f"\n❌ ERRORS:")
        print(f"   {result.get('error')}")
    
    # Save full results to file
    output_file = "agent_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full results saved to: {output_file}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ AGENT FAILED!")
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
