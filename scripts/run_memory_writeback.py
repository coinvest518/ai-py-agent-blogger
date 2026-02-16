from src.agent.graph import record_memory_outcomes_node
from src.agent.memory_store import get_memory_store
import json

state = {
    "ai_strategy": {"topic": "AI automation", "products": [{"name": "AI Boost Pro"}]},
    "tweet_text": "Test tweet for memory writeback",
    "twitter_post_id": "1234567890",
    "twitter_url": "https://twitter.com/user/status/1234567890",
    "facebook_status": "Posted: 111",
    "linkedin_status": "Posted",
    "instagram_status": "Posted",
    "telegram_status": "Posted: 999",
    "image_url": None,
    "blog_title": None
}

print('--- Calling record_memory_outcomes_node ---')
res = record_memory_outcomes_node(state)
print('Result:', res)

mem = get_memory_store()
print('\n--- Top Twitter posts from memory (recent) ---')
print(json.dumps(mem.get_top_posts(platform='twitter', limit=5), indent=2))
print('\n--- Top products from memory ---')
print(json.dumps(mem.get_top_products(limit=10), indent=2))
