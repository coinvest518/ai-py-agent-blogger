"""Test the new telegram_agent_v2 with working v3 API format."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import telegram_agent as telegram_agent_v2
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("TELEGRAM AGENT V2 - COMPREHENSIVE TEST")
print("=" * 70)

# Test 1: Get Bot Info
print("\n🤖 Test 1: Get Bot Info")
print("-" * 70)
result = telegram_agent_v2.get_bot_info()

if result["success"]:
    bot_data = result["data"]
    if "result" in bot_data:
        bot_data = bot_data["result"]
    
    bot_username = bot_data.get("username")
    bot_name = bot_data.get("first_name")
    bot_id = bot_data.get("id")
    
    print(f"✅ Bot Connected!")
    print(f"   Username: @{bot_username}")
    print(f"   Name: {bot_name}")
    print(f"   ID: {bot_id}")
else:
    print(f"❌ Failed: {result['error']}")
    sys.exit(1)

# Test 2: Get Updates
print(f"\n📥 Test 2: Get Updates (Check for available chats)")
print("-" * 70)
result = telegram_agent_v2.get_updates(limit=100)

available_chats = []

if result["success"]:
    data = result["data"]
    updates = data.get("result", []) if "result" in data else data
    
    print(f"✅ Got {len(updates)} updates")
    
    # Extract chat IDs
    seen_chats = set()
    for update in updates:
        msg = update.get("message") or update.get("channel_post")
        if msg and "chat" in msg:
            chat = msg["chat"]
            chat_id = chat.get("id")
            if chat_id and chat_id not in seen_chats:
                chat_info = {
                    "id": chat_id,
                    "title": chat.get("title") or chat.get("username") or "Private",
                    "type": chat.get("type"),
                    "username": chat.get("username")
                }
                available_chats.append(chat_info)
                seen_chats.add(chat_id)
    
    if available_chats:
        print(f"\n📊 Found {len(available_chats)} chat(s):")
        for chat in available_chats:
            username_str = f"@{chat['username']}" if chat.get('username') else "No username"
            print(f"\n   Chat ID: {chat['id']}")
            print(f"   Title: {chat['title']}")
            print(f"   Type: {chat['type']}")
            print(f"   Username: {username_str}")
            
            # Check for yieldbotdefi
            if chat.get('username') == 'yieldbotdefi' or 'yield' in chat['title'].lower():
                print(f"   🎯 THIS IS YOUR YIELD BOT DEFI GROUP!")
                print(f"   💡 Add to .env: TELEGRAM_GROUP_CHAT_ID={chat['id']}")
    else:
        print("\n⚠️ No chats found yet")
else:
    print(f"❌ Failed: {result['error']}")

# Test 3: Send message if we have a chat
if available_chats:
    print(f"\n✉️ Test 3: Send Test Message")
    print("-" * 70)
    
    # Send to first available chat
    test_chat = available_chats[0]
    chat_id = test_chat["id"]
    
    print(f"Sending test message to: {test_chat['title']} (ID: {chat_id})")
    
    result = telegram_agent_v2.send_message(
        chat_id=str(chat_id),
        text="🎉 *Telegram Agent V2 Working!*\n\nSuccessfully connected to FDWA AI automation system!\n\n✅ All systems operational 🤖",
        parse_mode="Markdown"
    )
    
    if result["success"]:
        print(f"✅ Message sent successfully!")
        print(f"   Log ID: {result.get('log_id')}")
        
        # If this is yieldbotdefi, give instructions
        if test_chat.get('username') == 'yieldbotdefi' or 'yield' in test_chat['title'].lower():
            print(f"\n🎊 SUCCESS! Your @yieldbotdefi group is connected!")
            print(f"\n💡 Update your .env file:")
            print(f"   TELEGRAM_GROUP_CHAT_ID={chat_id}")
    else:
        print(f"❌ Failed: {result['error']}")
else:
    print(f"\n📋 Test 3: No chats available for testing")
    print("-" * 70)
    print("\n📝 TO ENABLE TELEGRAM:")
    print(f"   1. Open Telegram app")
    print(f"   2. Go to @yieldbotdefi group")
    print(f"   3. Add bot: @{bot_username}")
    print(f"   4. Send a message: @{bot_username} hello")
    print(f"   5. Run this test again: python tests/test_telegram_agent_v2.py")

# Test 4: Test with configured group chat if set
group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")
if group_chat_id:
    print(f"\n✉️ Test 4: Send to Configured Group")
    print("-" * 70)
    
    result = telegram_agent_v2.send_to_group(
        "📢 Testing send_to_group() function!\n\nThis message uses the TELEGRAM_GROUP_CHAT_ID from .env"
    )
    
    if result["success"]:
        print(f"✅ Message sent to configured group!")
    else:
        print(f"❌ Failed: {result['error']}")

print("\n" + "=" * 70)
print("TESTING COMPLETE!")
print("=" * 70)

if available_chats:
    print("\n✅ Telegram is fully configured and working!")
    print("   You can now use telegram_agent_v2 in your automation workflows")
else:
    print("\n⏳ Telegram bot ready - waiting for group connection")
    print(f"   Add @{bot_username} to your @yieldbotdefi group to complete setup")
