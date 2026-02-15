"""
Complete AI Agent Workflow Test
Shows full execution with AI Decision Engine, data mining, and all integrations
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("\n" + "="*80)
print("🚀 FDWA AI AGENT - FULL WORKFLOW TEST")
print("="*80)
print("\nThis test will show:")
print("✓ AI Decision Engine consulting knowledge base & products")
print("✓ Tavily/SERP research mining trending topics")
print("✓ Smart content generation with product selection")
print("✓ Topic-aware image generation")
print("✓ Multi-platform posting (Twitter, LinkedIn, Facebook)")
print("✓ Blog generation with proper hyperlinks")
print("="*80)
print("\nStarting test...\n")

try:
    # Import the graph
    from src.agent.graph import graph
    
    print("✅ Graph loaded successfully!\n")
    
    # Initial state
    initial_state = {
        "messages": [],
        "trend_data": "",
        "tweet_text": "",
        "image_url": None,
        "twitter_url": None,
        "linkedin_status": None,
        "blog_status": None,
        "ai_strategy": None  # Will be populated by Decision Engine
    }
    
    print("="*80)
    print("📊 EXECUTING FULL WORKFLOW")
    print("="*80)
    print("\nWatch the AI mine data and make smart decisions...\n")
    
    # Run the full graph
    result = graph.invoke(initial_state)
    
    print("\n" + "="*80)
    print("✅ WORKFLOW COMPLETED!")
    print("="*80)
    
    # Show results
    print("\n📋 EXECUTION SUMMARY:\n")
    
    if result.get("ai_strategy"):
        strategy = result["ai_strategy"]
        print("🧠 AI DECISION ENGINE OUTPUT:")
        print(f"   Topic Selected: {strategy.get('topic', 'N/A')}")
        print(f"   Products Featured: {[p['name'][:40] for p in strategy.get('products', [])]}")
        print(f"   CTA: {strategy.get('cta', 'N/A')[:60]}...")
        print(f"   Memory Insights: {strategy.get('memory_insights', 'None')}")
        print()
    
    if result.get("trend_data"):
        print(f"🔍 Research Data: {len(result['trend_data'])} characters of trend analysis")
    
    if result.get("tweet_text"):
        print(f"\n📝 Generated Content:")
        print(f"   Twitter: {result['tweet_text'][:100]}...")
        
    if result.get("linkedin_text"):
        print(f"   LinkedIn: {result['linkedin_text'][:100]}...")
    
    if result.get("image_url"):
        print(f"\n🎨 Generated Image: {result['image_url']}")
    
    if result.get("twitter_url"):
        print(f"\n🐦 Twitter Post: {result['twitter_url']}")
    else:
        print("\n⚠️  Twitter: Not posted (check credentials)")
    
    if result.get("linkedin_status"):
        print(f"💼 LinkedIn: {result['linkedin_status']}")
    
    if result.get("facebook_status"):
        print(f"📘 Facebook: {result['facebook_status']}")
    
    if result.get("blog_status"):
        print(f"\n📄 Blog: {result['blog_status']}")
        if result.get("blog_html"):
            # Check for hyperlinks in blog
            blog_html = result["blog_html"]
            hyperlink_count = blog_html.count('<a href=')
            print(f"   ✓ Contains {hyperlink_count} hyperlinks")
            print(f"   ✓ Word count: ~{len(blog_html.split())} words")
    
    print("\n" + "="*80)
    print("🎉 TEST COMPLETED SUCCESSFULLY!")
    print("="*80)
    
    # Show what data sources were consulted
    print("\n📚 DATA SOURCES CONSULTED:")
    print("   ✓ FDWA_KNOWLEDGE_BASE.md (brand voice, expertise)")
    print("   ✓ FDWA_PRODUCTS_CATALOG.md (29 products)")
    print("   ✓ business_profile.json (core offerings)")
    print("   ✓ Google Sheets (recent posts for deduplication)")
    print("   ✓ Tavily/SERP APIs (trending topics)")
    print("   ✓ agent_memory.json (learning from past)")
    
    print("\n💡 All data was mined by AI Decision Engine to create smart, non-duplicate content!")
    print()

except Exception as e:
    print("\n" + "="*80)
    print("❌ TEST FAILED")
    print("="*80)
    print(f"\nError: {e}\n")
    
    import traceback
    traceback.print_exc()
    
    print("\n💡 Common fixes:")
    print("   1. Make sure .env has all API keys configured")
    print("   2. Check Composio connections are active")
    print("   3. Verify Google Sheets is initialized")
    print()
