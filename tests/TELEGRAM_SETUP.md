# Telegram Integration - Quick Setup

## ✅ Status: Bot Connected & Ready

**Your Bot**: [@ybotai_bot](https://t.me/ybotai_bot) (Yield Bot AI)

## 🚀 Quick Setup (2 minutes)

### Step 1: Add Bot to Your Group

1. Open Telegram and go to **@yieldbotdefi** group
2. Click group name → **Add Members**
3. Search for: **@ybotai_bot**
4. Add the bot to the group

### Step 2: Activate the Bot

Send this message in the group:
```
@ybotai_bot hello
```

### Step 3: Get Your Chat ID

Run this command:
```powershell
python get_chat_id_from_updates.py
```

It will show you the chat_id to add to your `.env` file.

### Step 4: Add Chat ID to .env

Add this line to your `.env` file:
```
TELEGRAM_GROUP_CHAT_ID=your_chat_id_here
```

### Step 5: Test It!

```powershell
python tests/test_telegram_agent_v2.py
```

You should see a success message in your Telegram group! 🎉

## 📝 Usage Examples

### Send a message to your group:

```python
from src.agent import telegram_agent

# Send to configured group
result = telegram_agent.send_to_group(
    "🤖 Hello from AI Agent!",
    parse_mode="Markdown"
)

# Or send to specific chat
result = telegram_agent.send_message(
    chat_id="your_chat_id",
    text="📊 Daily report is ready!"
)
```

### Integration with blog agent:

```python
from src.agent import telegram_agent
from src.agent.blog_email_agent import generate_blog_content

# Generate blog
blog_content = generate_blog_content()

# Notify on Telegram
telegram_agent.send_to_group(
    f"✅ New blog post generated!\n\nTitle: {blog_content['title']}"
)
```

### Get updates and respond:

```python
# Check for new messages
result = telegram_agent.get_updates(limit=10)

if result["success"]:
    updates = result["data"].get("result", [])
    for update in updates:
        if "message" in update:
            msg = update["message"]
            if "/status" in msg.get("text", ""):
                # Respond to status command
                telegram_agent.send_message(
                    chat_id=msg["chat"]["id"],
                    text="✅ All systems operational!"
                )
```

### Send photos or documents:

```python
# Send photo
telegram_agent.send_photo(
    chat_id="your_chat_id",
    photo="https://example.com/image.jpg",
    caption="📸 Generated image"
)

# Send poll
telegram_agent.send_poll(
    chat_id="your_chat_id",
    question="Which feature should we build next?",
    options=["Instagram Auto-post", "LinkedIn Scheduler", "Analytics Dashboard"]
)
```

## 🛠️ Available Functions

- `send_message()` - Send text messages
- `send_photo()` - Send images
- `send_document()` - Send files
- `send_poll()` - Send polls
- `send_location()` - Send GPS coordinates
- `get_updates()` - Receive new messages
- `get_bot_info()` - Bot details
- `get_chat_info()` - Chat information
- `edit_message()` - Edit sent messages
- `delete_message()` - Delete messages
- **`send_to_group()`** - Quick send to configured group

## 🔧 Troubleshooting

**"Chat not found" error?**
- Make sure bot is added to the group
- Send a message mentioning the bot
- Run `get_chat_id_from_updates.py` to get the correct chat_id

**No updates?**
- Bot must be active in at least one chat
- Send any message to the bot or in a group with the bot

**Need help?**
- Check `tests/test_telegram_agent_v2.py` for working examples
- View logs with detailed error messages
