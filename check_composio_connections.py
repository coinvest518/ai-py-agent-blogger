"""Check Composio connected accounts and help setup Telegram.

This script will show you what accounts are actually connected
and help you find the correct connected_account_id to use.
"""

import os
import requests
from dotenv import load_dotenv

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


if __name__ == "__main__":
    check_composio_connections()
