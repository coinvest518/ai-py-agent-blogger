"""Test Twitter Direct API (no Composio)."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.twitter_direct import TwitterDirectClient

def test_twitter_direct():
    """Test direct Twitter API posting with Bearer Token."""
    print("=" * 60)
    print("TWITTER DIRECT API TEST (No Composio)")
    print("=" * 60)
    
    # Test tweet content
    tweet_text = "🚀 Testing direct Twitter API integration!\n\nPosting without Composio using Bearer Token. #YieldBot #TestTweet"
    
    print(f"\n📝 Tweet content ({len(tweet_text)} chars):")
    print("-" * 60)
    print(tweet_text)
    print("-" * 60)
    
    try:
        # Initialize client
        print("\n🔑 Initializing Twitter client...")
        client = TwitterDirectClient()
        print(f"✅ Client initialized with {client.auth_method} authentication")
        
        # Create tweet
        print("\n📤 Posting tweet...")
        result = client.create_tweet(tweet_text)
        
        # Extract tweet info
        tweet_data = result.get("data", {})
        tweet_id = tweet_data.get("id")
        tweet_url = f"https://twitter.com/user/status/{tweet_id}" if tweet_id else None
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"Tweet ID: {tweet_id}")
        print(f"Tweet URL: {tweet_url}")
        print(f"Response: {result}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ FAILED!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        
        # Provide debugging hints
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\n💡 Your Bearer Token might be invalid or expired")
            print("   Get a new one at: https://developer.twitter.com/en/portal/dashboard")
        elif "403" in str(e) or "Forbidden" in str(e):
            print("\n💡 Your Twitter app needs elevated access or to be in a Project")
            print("   1. Go to: https://developer.twitter.com/en/portal/dashboard")
            print("   2. Create a Project")
            print("   3. Add your app to the project")
            print("   4. Generate new keys from the project")
        elif "429" in str(e):
            print("\n💡 Rate limit exceeded - wait a few minutes")
        
        return False

if __name__ == "__main__":
    print("\n🔧 Testing Twitter Direct API...\n")
    success = test_twitter_direct()
    
    if success:
        print("\n🎉 Twitter Direct API is working!")
    else:
        print("\n⚠️  Twitter Direct API test failed - see errors above")
