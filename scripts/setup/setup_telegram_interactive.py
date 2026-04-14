"""Test bot with direct commands and show setup instructions."""

import os
import requests
import webbrowser
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("COMPOSIO_API_KEY")
user_id = os.getenv("TELEGRAM_ENTITY_ID")

print("=" * 70)
print("TELEGRAM BOT SETUP & TEST")
print("=" * 70)

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}

# Get bot info
print("\n🤖 Step 1: Getting bot info...")
url = "https://backend.composio.dev/api/v3/tools/execute/TELEGRAM_GET_ME"
payload = {"user_id": user_id, "arguments": {}}

try:
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        
        if result.get("successful"):
            bot_data = result.get("data", {}).get("result", {})
            bot_username = bot_data.get("username")
            bot_name = bot_data.get("first_name")
            bot_id = bot_data.get("id")
            
            print(f"✅ Bot is active!")
            print(f"   Username: @{bot_username}")
            print(f"   Name: {bot_name}")
            print(f"   ID: {bot_id}")
            
            print(f"\n{'='*70}")
            print(f"📱 QUICK SETUP - DO THIS NOW:")
            print(f"{'='*70}")
            
            print(f"\n1️⃣ OPEN THE BOT:")
            bot_url = f"https://t.me/{bot_username}"
            print(f"   Click this link: {bot_url}")
            print(f"   (Opening in browser now...)")
            
            try:
                webbrowser.open(bot_url)
            except:
                pass
            
            print(f"\n2️⃣ START THE BOT:")
            print(f"   • Click the START button")
            print(f"   • Or type: /start")
            
            print(f"\n3️⃣ ADD TO YOUR GROUP:")
            print(f"   • In Telegram, go to your @yieldbotdefi group")
            print(f"   • Click group name → 'Add members'")
            print(f"   • Search: @{bot_username}")
            print(f"   • Add the bot")
            
            print(f"\n4️⃣ SEND A MESSAGE:")
            print(f"   • In the @yieldbotdefi group, type:")
            print(f"     Hello @{bot_username}")
            
            print(f"\n5️⃣ RUN THIS TEST AGAIN:")
            print(f"   python test_send_message_now.py")
            
            print(f"\n{'='*70}")
            print(f"⏰ WAITING FOR YOU TO ADD THE BOT...")
            print(f"{'='*70}")
            
            input(f"\n✋ Press ENTER after you've added @{bot_username} to @yieldbotdefi and sent a message...")
            
            # Now check for updates
            print(f"\n🔍 Checking for updates...")
            url2 = "https://backend.composio.dev/api/v3/tools/execute/TELEGRAM_GET_UPDATES"
            payload2 = {"user_id": user_id, "arguments": {"limit": 100}}
            
            response2 = requests.post(url2, headers=headers, json=payload2)
            
            if response2.status_code == 200:
                result2 = response2.json()
                
                if result2.get("successful"):
                    data = result2.get("data", {})
                    updates = data.get("result", [])
                    
                    print(f"✅ Got {len(updates)} updates!")
                    
                    if updates:
                        print(f"\n📊 Chats found:")
                        for update in updates:
                            msg = update.get("message") or update.get("my_chat_member", {})
                            if isinstance(msg, dict) and "chat" in msg:
                                chat = msg["chat"]
                                print(f"\n   Chat ID: {chat.get('id')}")
                                print(f"   Title: {chat.get('title') or chat.get('username') or 'Private'}")
                                print(f"   Type: {chat.get('type')}")
                                
                                # Try sending to this chat
                                test_chat_id = chat.get("id")
                                print(f"\n   🧪 Sending test message...")
                                
                                url3 = "https://backend.composio.dev/api/v3/tools/execute/TELEGRAM_SEND_MESSAGE"
                                payload3 = {
                                    "user_id": user_id,
                                    "arguments": {
                                        "chat_id": str(test_chat_id),
                                        "text": f"🎉 *SUCCESS!* Bot is connected and working!\n\n✅ FDWA AI Agent is now active in this chat!\n\nReady for automation! 🤖",
                                        "parse_mode": "Markdown"
                                    }
                                }
                                
                                response3 = requests.post(url3, headers=headers, json=payload3)
                                
                                if response3.status_code == 200:
                                    result3 = response3.json()
                                    
                                    if result3.get("successful"):
                                        print(f"   ✅ TEST MESSAGE SENT!")
                                    else:
                                        print(f"   ❌ Failed: {result3.get('error')}")
                    else:
                        print(f"\n⚠️ No updates yet. Make sure you:")
                        print(f"   1. Started the bot (@{bot_username})")
                        print(f"   2. Added it to @yieldbotdefi group")
                        print(f"   3. Sent a message in the group")
            
        else:
            print(f"❌ Failed: {result.get('error')}")
    else:
        print(f"❌ HTTP {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
