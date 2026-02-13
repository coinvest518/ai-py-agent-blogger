"""Get chat_id from recent Telegram updates after bot is added to group."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("COMPOSIO_API_KEY")
user_id = os.getenv("TELEGRAM_ENTITY_ID")

print("=" * 70)
print("GET CHAT ID FROM TELEGRAM UPDATES")
print("=" * 70)

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}

# Get recent updates
url = "https://backend.composio.dev/api/v3/tools/execute/TELEGRAM_GET_UPDATES"
payload = {
    "user_id": user_id,
    "arguments": {"limit": 100}
}

print("\n🔍 Fetching recent updates...")

try:
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        
        if result.get("successful"):
            data = result.get("data", {})
            if "result" in data:
                updates = data["result"]
            else:
                updates = data
            
            print(f"✅ Got {len(updates)} updates\n")
            
            # Extract unique chats
            chats = {}
            for update in updates:
                # Check various update types
                msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member", {}).get("chat")
                
                if msg and "chat" in msg:
                    chat = msg["chat"]
                    chat_id = chat.get("id")
                    chat_type = chat.get("type")
                    chat_title = chat.get("title") or chat.get("username") or chat.get("first_name", "Unknown")
                    chat_username = chat.get("username")
                    
                    if chat_id and chat_id not in chats:
                        chats[chat_id] = {
                            "title": chat_title,
                            "type": chat_type,
                            "username": chat_username
                        }
            
            if chats:
                print(f"📊 Found {len(chats)} unique chat(s):\n")
                
                for chat_id, info in chats.items():
                    username_str = f"@{info['username']}" if info.get('username') else "No username"
                    print(f"   Chat ID: {chat_id}")
                    print(f"   Title: {info['title']}")
                    print(f"   Type: {info['type']}")
                    print(f"   Username: {username_str}")
                    
                    # Check if this is yieldbotdefi
                    if info.get('username') == 'yieldbotdefi' or 'yield' in info['title'].lower():
                        print(f"   🎯 THIS IS YOUR GROUP!")
                        print(f"\n💡 Add to .env:")
                        print(f"   TELEGRAM_GROUP_CHAT_ID={chat_id}")
                    print()
            else:
                print("⚠️ No chats found in updates")
                print("\n📝 Make sure:")
                print("   1. Bot (@ybotai_bot) is added to @yieldbotdefi group")
                print("   2. Send a message in the group")
                print("   3. Run this script again")
        else:
            print(f"❌ Not successful: {result}")
    else:
        print(f"❌ Failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
