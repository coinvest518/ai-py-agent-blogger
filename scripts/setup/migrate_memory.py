"""Migration script to move from agent_memory.json to LangGraph memory store.

Run this once to transfer your existing memory data to the new system:
    python migrate_memory.py
"""

import json
import logging
from pathlib import Path

from src.agent.memory_store import get_memory_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MEMORY_JSON_PATH = BASE_DIR / "agent_memory.json"


def migrate_memory():
    """Migrate from agent_memory.json to LangGraph memory store."""
    
    logger.info("=" * 60)
    logger.info("MEMORY MIGRATION: JSON → LangGraph Store")
    logger.info("=" * 60)
    
    # Check if old memory file exists
    if not MEMORY_JSON_PATH.exists():
        logger.warning(f"⚠️  No memory file found at {MEMORY_JSON_PATH}")
        logger.info("Creating new empty memory store...")
        store = get_memory_store()
        logger.info("✅ New memory store created!")
        return
    
    # Load old memory
    try:
        with open(MEMORY_JSON_PATH, 'r', encoding='utf-8') as f:
            old_memory = json.load(f)
        logger.info(f"📖 Loaded old memory from {MEMORY_JSON_PATH}")
    except Exception as e:
        logger.error(f"❌ Failed to load old memory: {e}")
        return
    
    # Get memory store
    store = get_memory_store()
    
    # Migrate data
    logger.info("\n🔄 Migrating data...")
    
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
    logger.info(f"✅ Migrated {len(success_topics)} successful topics")
    
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
    logger.info(f"✅ Migrated {len(product_mentions)} products with {sum(product_mentions.values())} total mentions")
    
    # 3. Best posting times
    best_times = old_memory.get("best_posting_times", {})
    if best_times:
        store.save_user_preference("best_posting_times", best_times)
        logger.info(f"✅ Migrated best posting times: {best_times}")
    
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
    logger.info(f"✅ Migrated {len(high_engagement)} high engagement posts")
    
    # 5. Failed attempts
    failed = old_memory.get("failed_attempts", [])
    if failed:
        store.save_user_preference("failed_attempts", failed)
        logger.info(f"✅ Migrated {len(failed)} failed attempts")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ MIGRATION COMPLETE!")
    logger.info("=" * 60)
    logger.info("\n📝 Next steps:")
    logger.info("1. Your old memory is preserved in agent_memory.json")
    logger.info("2. New memory store is active and ready to use")
    logger.info("3. Update your code to use memory_store instead of JSON")
    logger.info("\n💡 The AI Decision Engine will automatically use the")
    logger.info("   memory store by default. No code changes needed!")
    
    # Create backup
    backup_path = MEMORY_JSON_PATH.with_suffix('.json.backup')
    try:
        with open(MEMORY_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
        logger.info(f"\n💾 Backup created: {backup_path}")
    except Exception as e:
        logger.warning(f"Could not create backup: {e}")


if __name__ == "__main__":
    migrate_memory()
