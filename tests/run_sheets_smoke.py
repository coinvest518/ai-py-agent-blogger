import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.agent.sheets_agent import save_post_to_sheets, save_token_to_sheets, search_posts_in_sheets, search_tokens_in_sheets

print("=== Google Sheets Smoke Test ===\n")

print("1. Saving test post...")
result = save_post_to_sheets('test','Integration smoke test post with $BTC mention','smoke_001', metadata={'engagement':'0','hash':'smoke001'})
print(f"   Result: {result}\n")

print("2. Saving test token...")
result = save_token_to_sheets('BTC', name='Bitcoin', source='smoke_test', notes='Smoke test integration')
print(f"   Result: {result}\n")

print("3. Searching for recent test posts...")
posts = search_posts_in_sheets(platform='test', days_back=7)
print(f"   Found {len(posts)} test posts")
if posts:
    print(f"   Latest: {posts[0].get('content_preview', '')[:50]}...\n")
else:
    print("   (No posts found - may need to wait for API sync)\n")

print("4. Searching for BTC tokens...")
tokens = search_tokens_in_sheets(symbol='BTC')
print(f"   Found {len(tokens)} BTC mentions")
if tokens:
    print(f"   Latest: {tokens[0].get('notes', '') or tokens[0].get('source', '')}\n")
else:
    print("   (No tokens found - may need to wait for API sync)\n")

print("=== Smoke Test Complete ===")
