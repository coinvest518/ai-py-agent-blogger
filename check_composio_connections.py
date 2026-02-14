"""Check Composio connected accounts and help diagnose Twitter 403 errors.

This script will show you what accounts are actually connected,
test Twitter specifically, and provide fix instructions for 403 errors.
"""

import os
import requests
from dotenv import load_dotenv
from composio import Composio

load_dotenv()

def check_composio_connections():
    """Check all connected accounts in Composio."""
    print("\n" + "=" * 70)
    print("COMPOSIO CONNECTED ACCOUNTS CHECK")
    print("=" * 70)
    
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        print("❌ COMPOSIO_API_KEY not found in .env")
        return
    
    print(f"\n📋 API Key: {api_key[:20]}...")
    
    # Use Composio REST API to get connections
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Get all connected accounts
    print("\n🔍 Fetching connected accounts...")
    twitter_account_id = None
    try:
        response = requests.get(
            "https://backend.composio.dev/api/v1/connectedAccounts",
            headers=headers
        )
        
        if response.status_code == 200:
            accounts = response.json().get("items", [])
            print(f"\n✅ Found {len(accounts)} connected account(s):")
            
            telegram_found = False
            for account in accounts:
                app_name = account.get("appName", "Unknown")
                account_id = account.get("id")
                status = account.get("status", "Unknown")
                
                print(f"\n   {'='*60}")
                print(f"   App: {app_name}")
                print(f"   Connected Account ID: {account_id}")
                print(f"   Status: {status}")
                
                if app_name.lower() == "telegram":
                    telegram_found = True
                    print(f"   🎯 THIS IS YOUR TELEGRAM CONNECTION!")
                    print(f"\n   💡 Update your .env file:")
                    print(f"      TELEGRAM_ACCOUNT_ID={account_id}")
                
                if app_name.lower() == "twitter":
                    twitter_account_id = account_id
                    print(f"   🐦 THIS IS YOUR TWITTER CONNECTION!")
                    if status.upper() != "ACTIVE":
                        print(f"   ⚠️  Status is {status} - may need reconnection!")
            
            if not telegram_found:
                print("\n" + "="*70)
                print("⚠️  NO TELEGRAM ACCOUNT CONNECTED YET!")
                print("="*70)
                print("\n📝 TO CONNECT TELEGRAM:")
                print("   1. Go to: https://app.composio.dev/")
                print("   2. Navigate to 'Telegram' toolkit")
                print("   3. Click 'Connect Account'")
                print("   4. Authenticate your Telegram bot")
                print("   5. Run this script again to get the connected_account_id")
                print("\n📌 Current Auth Config: ac_k90vyPaiJsDh")
                print("   (This is NOT the same as connected_account_id)")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get auth configs
    print("\n\n🔍 Checking Auth Configs...")
    try:
        response = requests.get(
            "https://backend.composio.dev/api/v1/auth-configs",
            headers=headers
        )
        
        if response.status_code == 200:
            configs = response.json().get("items", [])
            print(f"\n✅ Found {len(configs)} auth config(s):")
            
            for config in configs:
                app_name = config.get("appName", "Unknown")
                config_id = config.get("id")
                
                if app_name.lower() == "telegram":
                    print(f"\n   App: {app_name}")
                    print(f"   Auth Config ID: {config_id}")
                    if config_id == "ac_k90vyPaiJsDh":
                        print(f"   ✅ This matches your .env file!")
                        
    except Exception as e:
        print(f"❌ Error checking auth configs: {e}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Auth Config ID (ac_...) = Configuration template for authentication
Connected Account ID (ca_...) = Actual authenticated account connection

You currently have the Auth Config, but need to CONNECT an account.
Once connected, you'll get a new ID (starting with ca_) to use in your code.
    """)
    
    # Test Twitter specifically
    if twitter_account_id:
        print("\n" + "=" * 70)
        print("🐦 TESTING TWITTER CONNECTION")
        print("=" * 70)
        test_twitter_connection(twitter_account_id)
    
    return twitter_account_id


def test_twitter_connection(twitter_account_id):
    """Test Twitter connection and diagnose 403 errors."""
    print(f"\n🔍 Testing Twitter posting capability...")
    print(f"   Account ID: {twitter_account_id}")
    
    try:
        composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
        
        # Try to get Twitter user info (read-only test)
        print("\n   📤 Attempting test Twitter API call...")
        result = composio_client.tools.execute(
            "TWITTER_USER_LOOKUP_ME",
            {},
            connected_account_id=twitter_account_id
        )
        
        if result.get("successful"):
            print("\n   ✅ Twitter connection is WORKING!")
            username = result.get("data", {}).get("data", {}).get("username", "Unknown")
            print(f"   📍 Connected as: @{username}")
            print("\n   🎉 You can post tweets! Your setup is correct.")
        else:
            error = result.get("error", "Unknown error")
            print(f"\n   ❌ Twitter API Error: {error}")
            
            # Diagnose specific errors
            if "403" in str(error) and "client-not-enrolled" in str(error):
                print("\n" + "=" * 70)
                print("⚠️  DIAGNOSIS: Twitter App NOT in Project")
                print("=" * 70)
                print("""
This is the "client-not-enrolled" error. Your Twitter app is NOT attached
to a Project, which is REQUIRED for Twitter API v2.

🔧 FIX (5 minutes):

1. Go to: https://developer.twitter.com/en/portal/dashboard

2. Create a Project:
   - Click "+ Add Project" 
   - Name it: "YieldBot AI"
   - Describe use case: "AI social media automation"

3. Attach your app to the project:
   - During project creation, select your existing app
   OR
   - Go to project → Apps → Add App → Select your app

4. Regenerate keys IN THE PROJECT:
   - Go to project → Your App → "Keys and tokens" tab
   - Regenerate Bearer Token
   - Regenerate Access Token & Secret
   - SAVE THEM (shown only once!)

5. Reconnect in Composio:
   - Go to: https://app.composio.dev/
   - Find Twitter → Click "Reconnect"
   - Authorize with your account

6. Run this script again to verify!

📖 Full guide: See TWITTER_FIX_GUIDE.md in this folder
                """)
            elif "401" in str(error) or "Unauthorized" in str(error):
                print("\n   💡 Authentication expired - reconnect at https://app.composio.dev/")
            elif "EXPIRED" in str(error):
                print("\n   💡 Connection expired - reconnect at https://app.composio.dev/")
                
    except Exception as e:
        print(f"\n   ❌ Test failed: {e}")
        print(f"   💡 Check your Composio connection at: https://app.composio.dev/")


if __name__ == "__main__":
    check_composio_connections()
