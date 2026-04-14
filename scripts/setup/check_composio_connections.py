"""Check Composio connected accounts and help diagnose Twitter 403 errors.

This script will show you what accounts are actually connected,
test Twitter specifically, and provide fix instructions for 403 errors.
"""

import os
import logging

import requests
from dotenv import load_dotenv
from composio import Composio

load_dotenv()
logger = logging.getLogger(__name__)


def check_composio_connections():
    """Check all connected accounts in Composio."""
    logger.info("%s", "=" * 70)
    logger.info("COMPOSIO CONNECTED ACCOUNTS CHECK")
    logger.info("%s", "=" * 70)
    
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        logger.error("COMPOSIO_API_KEY not found in .env")
        return
    
    logger.info("API Key: %s...", api_key[:20])
    
    # Use Composio REST API to get connections
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Get all connected accounts
    logger.info("Fetching connected accounts...")
    twitter_account_id = None
    try:
        response = requests.get(
            "https://backend.composio.dev/api/v1/connectedAccounts",
            headers=headers
        )
        
        if response.status_code == 200:
            accounts = response.json().get("items", [])
            logger.info("Found %d connected account(s).", len(accounts))
            
            telegram_found = False
            for account in accounts:
                app_name = account.get("appName", "Unknown")
                account_id = account.get("id")
                status = account.get("status", "Unknown")
                
                logger.info("%s", "=" * 60)
                logger.info("App: %s", app_name)
                logger.info("Connected Account ID: %s", account_id)
                logger.info("Status: %s", status)
                
                if app_name.lower() == "telegram":
                    telegram_found = True
                    logger.info("🎯 THIS IS YOUR TELEGRAM CONNECTION!")
                    logger.info("Update your .env file:")
                    logger.info("TELEGRAM_ACCOUNT_ID=%s", account_id)
                
                if app_name.lower() == "twitter":
                    twitter_account_id = account_id
                    logger.info("🐦 THIS IS YOUR TWITTER CONNECTION!")
                    if status.upper() != "ACTIVE":
                        logger.warning("Status is %s - may need reconnection", status)
            
            if not telegram_found:
                logger.warning("NO TELEGRAM ACCOUNT CONNECTED YET!")
                logger.info("TO CONNECT TELEGRAM:")
                logger.info("  1. Go to: https://app.composio.dev/")
                logger.info("  2. Navigate to 'Telegram' toolkit")
                logger.info("  3. Click 'Connect Account'")
                logger.info("  4. Authenticate your Telegram bot")
                logger.info("  5. Run this script again to get the connected_account_id")
                logger.info("Current Auth Config: ac_k90vyPaiJsDh")
                logger.info("(This is NOT the same as connected_account_id)")
                
        else:
            logger.error("API Error: %s", response.status_code)
            logger.debug("Response: %s", response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get auth configs
    logger.info("Checking Auth Configs...")
    try:
        response = requests.get(
            "https://backend.composio.dev/api/v1/auth-configs",
            headers=headers
        )
        
        if response.status_code == 200:
            configs = response.json().get("items", [])
            logger.info("Found %d auth config(s).", len(configs))
            
            for config in configs:
                app_name = config.get("appName", "Unknown")
                config_id = config.get("id")
                
                if app_name.lower() == "telegram":
                    logger.info("App: %s", app_name)
                    logger.info("Auth Config ID: %s", config_id)
                    if config_id == "ac_k90vyPaiJsDh":
                        logger.info("This matches your .env file!")
    except Exception as e:
        print(f"❌ Error checking auth configs: {e}")
    
    logger.info("%s", "=" * 70)
    logger.info("SUMMARY")
    logger.info("%s", "=" * 70)
    logger.info(
        "Auth Config ID (ac_...) = Configuration template for authentication\n"
        "Connected Account ID (ca_...) = Actual authenticated account connection\n\n"
        "You currently have the Auth Config, but need to CONNECT an account.\n"
        "Once connected, you'll get a new ID (starting with ca_) to use in your code."
    )
    
    # Test Twitter specifically
    if twitter_account_id:
        logger.info("%s", "=" * 70)
        logger.info("TESTING TWITTER CONNECTION")
        logger.info("%s", "=" * 70)
        test_twitter_connection(twitter_account_id)
    
    return twitter_account_id


def test_twitter_connection(twitter_account_id):
    """Test Twitter connection and diagnose 403 errors."""
    logger.info("Testing Twitter posting capability...")
    logger.info("Account ID: %s", twitter_account_id)
    
    try:
        composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
        
        # Try to get Twitter user info (read-only test)
        logger.info("Attempting test Twitter API call...")
        result = composio_client.tools.execute(
            "TWITTER_USER_LOOKUP_ME",
            {},
            connected_account_id=twitter_account_id
        )
        
        if result.get("successful"):
            logger.info("Twitter connection is WORKING!")
            username = result.get("data", {}).get("data", {}).get("username", "Unknown")
            logger.info("Connected as: @%s", username)
            logger.info("You can post tweets! Your setup is correct.")
        else:
            error = result.get("error", "Unknown error")
            logger.error("Twitter API Error: %s", error)
            
            # Diagnose specific errors
            if "403" in str(error) and "client-not-enrolled" in str(error):
                logger.warning("DIAGNOSIS: Twitter App NOT in Project")
                logger.info(
                    "This is the 'client-not-enrolled' error. Your Twitter app is NOT attached "
                    "to a Project, which is REQUIRED for Twitter API v2. See TWITTER_FIX_GUIDE.md"
                )
            elif "401" in str(error) or "Unauthorized" in str(error):
                logger.info("Authentication expired - reconnect at https://app.composio.dev/")
            elif "EXPIRED" in str(error):
                logger.info("Connection expired - reconnect at https://app.composio.dev/")
                
    except Exception as e:
        logger.exception("Test failed: %s", e)
        logger.info("Check your Composio connection at: https://app.composio.dev/")


if __name__ == "__main__":
    check_composio_connections()
