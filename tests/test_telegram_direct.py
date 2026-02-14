"""Direct test of Composio Telegram connection.

Tests the Telegram connection using Composio directly without wrapper.
"""

import os
from composio import Composio
from dotenv import load_dotenv

load_dotenv()

def test_telegram_connection():
    """Test if Telegram is connected and working via Composio."""
    print("\n" + "=" * 60)
    print("TESTING COMPOSIO TELEGRAM CONNECTION")
    print("=" * 60)
    
    # Get credentials
    api_key = os.getenv("COMPOSIO_API_KEY")
    account_id = os.getenv("TELEGRAM_ACCOUNT_ID")
    entity_id = os.getenv("TELEGRAM_ENTITY_ID", "default")
    
    print(f"\n📋 Configuration:")
    print(f"   API Key: {api_key[:20]}..." if api_key else "   API Key: NOT SET")
    print(f"   Account ID: {account_id}")
    print(f"   Entity ID: {entity_id}")
    
    if not api_key:
        print("\n❌ COMPOSIO_API_KEY not found in .env")
        return
    
    if not account_id:
        print("\n❌ TELEGRAM_ACCOUNT_ID not found in .env")
        return
    
    # Initialize Composio
    print("\n🔧 Initializing Composio...")
    composio_client = Composio(api_key=api_key, entity_id=entity_id)
    
    # Test 1: Get Bot Info
    print("\n" + "-" * 60)
    print("TEST 1: Get Bot Info")
    print("-" * 60)
    try:
        result = composio_client.execute_action(
            action="TELEGRAM_GET_BOT_INFO",
            params={},
            entity_id=entity_id
        )
        print(f"✅ SUCCESS!")
        print(f"   Bot Data: {result}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 2: Send a message (need chat_id)
    print("\n" + "-" * 60)
    print("TEST 2: Send Message (Optional)")
    print("-" * 60)
    
    chat_id = input("Enter your Telegram chat ID to test sending (or press Enter to skip): ").strip()
    
    if chat_id:
        try:
            result = composio_client.execute_action(
                action="TELEGRAM_SEND_MESSAGE",
                params={
                    "chat_id": chat_id,
                    "text": "🤖 Test message from FDWA AI Agent via Composio!"
                },
                entity_id=entity_id
            )
            print(f"✅ MESSAGE SENT!")
            print(f"   Result: {result}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
    else:
        print("⏭ Skipped (no chat_id provided)")
    
    # Test 3: List available actions info
    print("\n" + "-" * 60)
    print("TEST 3: Connection Status")
    print("-" * 60)
    print(f"✅ Composio client initialized successfully")
    print(f"   Entity ID: {entity_id}")
    print(f"   Account ID: {account_id}")
    
    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print("\n💡 Tip: To get your chat ID, message @userinfobot on Telegram")


if __name__ == "__main__":
    test_telegram_connection()
