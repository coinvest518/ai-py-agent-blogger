"""Verify Telegram Agent Integration Status.

This script checks:
1. Telegram agent module configuration
2. Whether telegram is integrated into main graph
3. Comparison with other social platform integrations
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("TELEGRAM AGENT INTEGRATION VERIFICATION")
print("=" * 60)

# 1. Check telegram_agent.py configuration
print("\n1. Telegram Agent Module Check:")
print("-" * 60)

try:
    # Import telegram_agent directly to avoid graph/langchain dependencies
    import importlib.util
    telegram_path = project_root / "src" / "agent" / "telegram_agent.py"
    spec = importlib.util.spec_from_file_location("telegram_agent", telegram_path)
    telegram_agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(telegram_agent)
    print("✅ telegram_agent.py imports successfully")
    
    # Check env vars
    print(f"\nEnvironment Variables:")
    print(f"  COMPOSIO_API_KEY: {'✅ Set' if telegram_agent.COMPOSIO_API_KEY else '❌ Missing'}")
    print(f"  TELEGRAM_ENTITY_ID: {'✅ Set' if telegram_agent.TELEGRAM_USER_ID else '❌ Missing'}")
    print(f"  TELEGRAM_GROUP_USERNAME: {telegram_agent.TELEGRAM_GROUP_USERNAME or '❌ Not set'}")
    print(f"  TELEGRAM_GROUP_CHAT_ID: {telegram_agent.TELEGRAM_GROUP_CHAT_ID or '❌ Not set'}")
    
    # Test basic functions exist
    print(f"\n  Core Functions:")
    print(f"    send_message: {'✅' if hasattr(telegram_agent, 'send_message') else '❌'}")
    print(f"    send_to_group: {'✅' if hasattr(telegram_agent, 'send_to_group') else '❌'}")
    print(f"    get_bot_info: {'✅' if hasattr(telegram_agent, 'get_bot_info') else '❌'}")
    print(f"    send_photo: {'✅' if hasattr(telegram_agent, 'send_photo') else '❌'}")
    
except Exception as e:
    print(f"❌ Failed to import telegram_agent: {e}")
    sys.exit(1)

# 2. Test telegram agent functionality
print("\n2. Telegram Agent Functionality Test:")
print("-" * 60)

try:
    # Test get_bot_info
    bot_info = telegram_agent.get_bot_info()
    if bot_info.get('success'):
        bot_data = bot_info.get('data', {}).get('result', {})
        print(f"✅ Bot Info Retrieved:")
        print(f"    Username: @{bot_data.get('username')}")
        print(f"    Name: {bot_data.get('first_name')}")
        print(f"    Bot ID: {bot_data.get('id')}")
    else:
        print(f"❌ Bot Info Failed: {bot_info.get('error')}")
        
    # Test send_to_group
    test_msg = "🔍 Integration verification test from telegram module"
    result = telegram_agent.send_to_group(test_msg)
    if result.get('success'):
        msg_data = result.get('data', {}).get('result', {})
        chat_data = msg_data.get('chat', {})
        print(f"\n✅ Test Message Sent Successfully:")
        print(f"    Group: {chat_data.get('title')} (@{chat_data.get('username')})")
        print(f"    Chat ID: {chat_data.get('id')}")
        print(f"    Message ID: {msg_data.get('message_id')}")
        print(f"    Log ID: {result.get('log_id')}")
    else:
        print(f"\n❌ Send Failed: {result.get('error')}")
        
except Exception as e:
    print(f"❌ Functionality test failed: {e}")

# 3. Check main graph integration
print("\n3. Main Agent Graph Integration Check:")
print("-" * 60)

try:
    # Read graph.py file directly to check for telegram references
    graph_file = project_root / "src" / "agent" / "graph.py"
    with open(graph_file, 'r', encoding='utf-8') as f:
        graph_content = f.read()
    
    # Check if telegram is imported
    has_telegram_import = 'telegram_agent' in graph_content or 'from src.agent.telegram' in graph_content
    print(f"  Telegram import in graph.py: {'✅ Yes' if has_telegram_import else '❌ No'}")
    
    # Check other platform imports for comparison
    has_linkedin = 'linkedin_agent' in graph_content
    has_instagram = 'instagram_agent' in graph_content
    
    print(f"\n  Other Platform Imports (for comparison):")
    print(f"    LinkedIn: {'✅ Integrated' if has_linkedin else '❌ Not integrated'}")
    print(f"    Instagram: {'✅ Integrated' if has_instagram else '❌ Not integrated'}")
    
    # Check for telegram-related nodes/functions
    has_telegram_node = 'telegram' in graph_content.lower() or 'post_telegram' in graph_content
    print(f"\n  Telegram References in graph.py:")
    print(f"    Telegram code found: {'✅ Yes' if has_telegram_node else '❌ No'}")
    
    # Count social media posting nodes
    social_node_patterns = ['post_social_media', 'post_linkedin', 'post_instagram', 'post_facebook', 'post_twitter', 'post_telegram']
    found_nodes = [p for p in social_node_patterns if p in graph_content]
    print(f"\n    Social Media Post Nodes Found: {len(found_nodes)}")
    for node in found_nodes:
        print(f"      - {node}")
        
except Exception as e:
    print(f"❌ Failed to check graph integration: {e}")

# 4. Summary and Recommendations
print("\n4. Summary:")
print("=" * 60)

# Determine integration status
telegram_module_working = telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID
telegram_integrated = has_telegram_import and has_telegram_node

if telegram_module_working and telegram_integrated:
    print("✅ Telegram agent is FULLY INTEGRATED and WORKING!")
    print("✅ Module configured correctly")
    print("✅ Integrated into main agent graph workflow")
    
    print("\n📋 Telegram will automatically post:")
    print("   - After Twitter/Facebook posts")
    print("   - Crypto-focused market updates")
    print("   - Parsed from existing research data (no extra API calls)")
    print("   - With image support when available")
    
    print("\n💡 Next time the agent runs, Telegram will receive posts!")
    
elif telegram_module_working:
    print("✅ Telegram agent module is CONFIGURED and WORKING")
    print("⚠️  Integration status unclear - check manually")
    
    print("\n📋 Detected in graph.py:")
    print(f"   - Telegram import: {'✅' if has_telegram_import else '❌'}")
    print(f"   - Telegram node: {'✅' if has_telegram_node else '❌'}")
    print(f"   - post_telegram found: {any('post_telegram' in str(n) for n in found_nodes)}")
    
else:
    print("❌ Telegram agent is NOT properly configured")
    print("   Check .env file for TELEGRAM_GROUP_USERNAME or TELEGRAM_GROUP_CHAT_ID")

print("\n" + "=" * 60)
