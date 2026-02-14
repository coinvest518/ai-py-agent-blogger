"""Test Twitter via Composio with correct account ID."""

import os
from dotenv import load_dotenv
from composio import Composio

load_dotenv()

composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
twitter_account_id = os.getenv("TWITTER_ACCOUNT_ID")

print(f"Testing Twitter with account ID: {twitter_account_id}\n")

# Simple test tweet
tweet_text = "🚀 Testing Composio Twitter integration! #YieldBot #TestPost"

print(f"Posting: {tweet_text}\n")

try:
    result = composio_client.tools.execute(
        "TWITTER_CREATION_OF_A_POST",
        {"text": tweet_text},
        connected_account_id=twitter_account_id
    )
    
    print(f"✅ SUCCESS!")
    print(f"Result: {result}")
    
    if result.get("successful"):
        tweet_id = result.get("data", {}).get("data", {}).get("id")
        print(f"\nTweet ID: {tweet_id}")
        print(f"URL: https://twitter.com/user/status/{tweet_id}")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    
    error_str = str(e)
    if "client-not-enrolled" in error_str or "403" in error_str:
        print("\n" + "="*70)
        print("⚠️  Your Twitter app needs to be in a Project!")
        print("="*70)
        print("\n📖 See TWITTER_FIX_GUIDE.md for step-by-step fix")
        print("    Or go to: https://developer.twitter.com/en/portal/dashboard")
