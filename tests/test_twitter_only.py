"""Test Twitter posting in isolation - DIRECT API (no Composio)."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the actual functions from graph.py and direct Twitter client
from src.agent.graph import _adapt_for_twitter
from src.agent.twitter_direct import post_tweet_direct

def test_twitter_posting():
    """Test Twitter posting with sample content."""
    print("=" * 60)
    print("TWITTER POSTING TEST")
    print("=" * 60)
    
    # Sample research data (crypto-focused to match Telegram test)
    sample_research = """
    Bitcoin (BTC) hits new all-time high above $100k. 
    Ethereum (ETH) DeFi protocols see massive growth.
    AI-powered trading bots gaining popularity in crypto markets.
    Smart contract automation revolutionizing DeFi yield farming.
    """
    
    print("\n📊 Research Data:")
    print(sample_research.strip())
    
    # Adapt content for Twitter using actual function from graph.py
    print("\n🐦 Adapting content for Twitter...")
    twitter_content = _adapt_for_twitter(sample_research)
    
    print("\n✅ Generated Twitter Content:")
    print("-" * 60)
    print(twitter_content)
    print("-" * 60)
    print(f"📏 Character count: {len(twitter_content)}/280")
    
    if len(twitter_content) > 280:
        print("⚠️  WARNING: Tweet exceeds 280 character limit!")
    else:
        print("✅ Character count OK")
    
    # Test actual posting with DIRECT Twitter API (no Composio!)
    print("\n🚀 Attempting to post to Twitter via DIRECT API...")
    print("(Bypassing Composio - using your Twitter credentials directly)")
    
    try:
        # Post directly to Twitter API v2
        result = post_tweet_direct(text=twitter_content)
        
        print("\n✅ TWITTER POST SUCCESSFUL!")
        print(f"Tweet ID: {result.get('tweet_id')}")
        print(f"Tweet URL: {result.get('tweet_url')}")
        
        return True
            
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Twitter posting failed!")
        print(f"Error: {error_msg}")
        print(f"Error type: {type(e).__name__}")
        
        # Provide helpful debugging info
        if "401" in error_msg or "Unauthorized" in error_msg:
            print("\n💡 Authentication issue - check your Twitter credentials:")
            print("   TWITTER_API_KEY, TWITTER_API_SECRET")
            print("   TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
        elif "403" in error_msg or "Forbidden" in error_msg:
            print("\n💡 Permission denied - make sure your Twitter app has:")
            print("   • Read and Write permissions")
            print("   • Is attached to a Project (Twitter API v2 requirement)")
        elif "429" in error_msg:
            print("\n💡 Rate limit exceeded - wait a few minutes")
        
        return False

if __name__ == "__main__":
    print("\n🔧 Testing Twitter posting functionality...\n")
    
    success = test_twitter_posting()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TWITTER TEST PASSED")
    else:
        print("❌ TWITTER TEST FAILED")
    print("=" * 60)
