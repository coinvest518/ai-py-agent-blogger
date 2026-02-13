"""Test and example usage of Telegram Agent.

This script demonstrates how to use the Telegram agent to send messages,
photos, documents, and interact with Telegram chats.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import telegram_agent
from dotenv import load_dotenv

load_dotenv()


def test_bot_info():
    """Test getting bot information."""
    print("\n=== Testing Bot Info ===")
    result = telegram_agent.get_bot_info()
    if result["success"]:
        print(f"✅ Bot Info Retrieved: {result['data']}")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_send_message(chat_id: str):
    """Test sending a simple text message."""
    print("\n=== Testing Send Message ===")
    result = telegram_agent.send_message(
        chat_id=chat_id,
        text="🤖 Hello from FDWA AI Automation Agency! This is a test message from our Telegram agent.",
        parse_mode="HTML",
        disable_notification=False
    )
    if result["success"]:
        print(f"✅ Message Sent: {result['data']}")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_send_message_with_markup(chat_id: str):
    """Test sending a message with inline keyboard."""
    print("\n=== Testing Send Message with Inline Keyboard ===")
    
    # JSON-serialized inline keyboard
    reply_markup = '''{
        "inline_keyboard": [
            [
                {"text": "Visit Website", "url": "https://fdwa.com"},
                {"text": "Contact Us", "callback_data": "contact"}
            ],
            [
                {"text": "Learn More", "callback_data": "learn_more"}
            ]
        ]
    }'''
    
    result = telegram_agent.send_message(
        chat_id=chat_id,
        text="📱 Check out our services!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    if result["success"]:
        print(f"✅ Message with Inline Keyboard Sent")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_send_poll(chat_id: str):
    """Test sending a poll."""
    print("\n=== Testing Send Poll ===")
    result = telegram_agent.send_poll(
        chat_id=chat_id,
        question="What's your favorite AI automation use case?",
        options=[
            "Social Media Management",
            "Content Creation",
            "Customer Service",
            "Analytics & Insights"
        ],
        is_anonymous=True,
        allows_multiple_answers=True
    )
    if result["success"]:
        print(f"✅ Poll Sent")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_get_updates():
    """Test getting updates (messages, commands, etc.)."""
    print("\n=== Testing Get Updates ===")
    result = telegram_agent.get_updates(limit=10, timeout=5)
    if result["success"]:
        updates = result["data"].get("result", [])
        print(f"✅ Retrieved {len(updates)} updates")
        for update in updates[:3]:  # Show first 3
            print(f"  Update ID: {update.get('update_id')}")
            if "message" in update:
                msg = update["message"]
                print(f"    From: {msg.get('from', {}).get('username', 'Unknown')}")
                print(f"    Text: {msg.get('text', 'N/A')}")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_get_chat_info(chat_id: str):
    """Test getting chat information."""
    print("\n=== Testing Get Chat Info ===")
    result = telegram_agent.get_chat_info(chat_id)
    if result["success"]:
        print(f"✅ Chat Info Retrieved: {result['data']}")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_send_photo(chat_id: str, photo_url: str):
    """Test sending a photo."""
    print("\n=== Testing Send Photo ===")
    result = telegram_agent.send_photo(
        chat_id=chat_id,
        photo=photo_url,
        caption="📸 Check out this image from FDWA!",
        parse_mode="Markdown"
    )
    if result["success"]:
        print(f"✅ Photo Sent")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def test_send_location(chat_id: str):
    """Test sending a location."""
    print("\n=== Testing Send Location ===")
    # Example: Eiffel Tower coordinates
    result = telegram_agent.send_location(
        chat_id=chat_id,
        latitude=48.8584,
        longitude=2.2945
    )
    if result["success"]:
        print(f"✅ Location Sent")
    else:
        print(f"❌ Failed: {result['error']}")
    return result


def run_all_tests():
    """Run all Telegram agent tests."""
    print("=" * 60)
    print("TELEGRAM AGENT TEST SUITE")
    print("=" * 60)
    
    # Get chat ID from environment or prompt
    chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID")
    if not chat_id:
        chat_id = input("\nEnter your Telegram chat ID (or @channel_username): ")
    
    if not chat_id:
        print("❌ No chat ID provided. Exiting.")
        return
    
    # Run tests
    test_bot_info()
    test_send_message(chat_id)
    test_send_message_with_markup(chat_id)
    test_send_poll(chat_id)
    test_get_updates()
    test_get_chat_info(chat_id)
    
    # Optional: Test with photo URL
    photo_test = input("\nTest photo sending? (y/n): ").lower()
    if photo_test == 'y':
        photo_url = input("Enter photo URL: ")
        if photo_url:
            test_send_photo(chat_id, photo_url)
    
    # Optional: Test location
    location_test = input("\nTest location sending? (y/n): ").lower()
    if location_test == 'y':
        test_send_location(chat_id)
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
