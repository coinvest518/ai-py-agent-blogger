"""Simple migration script without complex imports."""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Direct import to avoid __init__.py issues
from agent.memory_store import AgentMemoryStore
from langgraph.store.memory import InMemoryStore

BASE_DIR = Path(__file__).parent
MEMORY_JSON_PATH = BASE_DIR / "agent_memory.json"

print("=" * 60)
print("MEMORY MIGRATION: JSON → LangGraph Store")
print("=" * 60)

# Check if old memory file exists
if not MEMORY_JSON_PATH.exists():
    print(f"\n⚠️  No memory file found at {MEMORY_JSON_PATH}")
    print("Creating new empty memory store...")
    store_backend = InMemoryStore()
    store = AgentMemoryStore(store=store_backend, user_id="fdwa_agent")
    print("✅ New memory store created!")
else:
    # Load old memory
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            old_memory = json.load(f)
        print(f"\n📖 Loaded old memory from {MEMORY_JSON_PATH}")
        print(f"   - {len(old_memory.get('successful_topics', []))} successful topics")
        print(f"   - {len(old_memory.get('product_mentions', {}))} products")
        print(f"   - {len(old_memory.get('high_engagement_posts', []))} high engagement posts")
    except Exception as e:
        print(f"❌ Failed to load old memory: {e}")
        sys.exit(1)
    
    # Get memory store
    store_backend = InMemoryStore()
    store = AgentMemoryStore(store=store_backend, user_id="fdwa_agent")
    
    # Migrate data
    print("\n🔄 Migrating data...")
    
    # 1. Successful topics
    success_topics = old_memory.get("successful_topics", [])
    for topic in success_topics:
        store.record_post_performance(
            topic=topic,
            platform="unknown",
            engagement=0,
            success=True,
            metadata={"migrated_from_json": True}
        )
    print(f"✅ Migrated {len(success_topics)} successful topics")
    
    # 2. Product mentions
    product_mentions = old_memory.get("product_mentions", {})
    for product, count in product_mentions.items():
        # Create multiple mention records
        for i in range(count):
            store.record_product_mention(
                product_name=product,
                platform="unknown",
                engagement=0,
                conversion=False
            )
    print(f"✅ Migrated {len(product_mentions)} products with {sum(product_mentions.values())} total mentions")
    
    # 3. Best posting times
    best_times = old_memory.get("best_posting_times", {})
    if best_times:
        store.save_user_preference("best_posting_times", best_times)
        print(f"✅ Migrated best posting times: {best_times}")
    
    # 4. High engagement posts
    high_engagement = old_memory.get("high_engagement_posts", [])
    for post in high_engagement:
        store.record_post_performance(
            topic=post.get("topic", "unknown"),
            platform=post.get("platform", "unknown"),
            engagement=post.get("engagement", 0),
            success=True,
            metadata={
                "migrated_from_json": True,
                "original_timestamp": post.get("timestamp")
            }
        )
    print(f"✅ Migrated {len(high_engagement)} high engagement posts")
    
    # 5. Failed attempts
    failed = old_memory.get("failed_attempts", [])
    if failed:
        store.save_user_preference("failed_attempts", failed)
        print(f"✅ Migrated {len(failed)} failed attempts")
    
    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 60)
    print("\n📝 Next steps:")
    print("1. Your old memory is preserved in agent_memory.json")
    print("2. New memory store is active and ready to use")
    print("3. The AI Decision Engine will automatically use memory store")
    
    # Create backup
    backup_path = MEMORY_JSON_PATH.with_suffix('.json.backup')
    try:
        with open(MEMORY_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
        print(f"\n💾 Backup created: {backup_path}")
    except Exception as e:
        print(f"⚠️  Could not create backup: {e}")

print("\n🎉 Migration process complete!\n")
