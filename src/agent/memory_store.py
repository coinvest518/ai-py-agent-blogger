"""Long-term memory store for FDWA AI Agent using LangGraph persistence.

This module provides persistent memory storage across agent runs:
- User preferences and behavior patterns
- Content performance tracking
- Product mention success rates
- Platform-specific insights
- Crypto trading patterns
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)

# Memory namespaces for organizing different types of data
NAMESPACE_USER_PREFS = ("user", "preferences")
NAMESPACE_CONTENT_PERF = ("content", "performance")
NAMESPACE_PRODUCTS = ("products", "mentions")
NAMESPACE_PLATFORMS = ("platforms", "insights")
NAMESPACE_CRYPTO = ("crypto", "insights")
NAMESPACE_GENERAL = ("agent", "general")


class AgentMemoryStore:
    """Manages long-term memory for the AI agent using LangGraph store."""
    
    def __init__(self, store: Optional[BaseStore] = None, user_id: str = "fdwa_agent"):
        """Initialize memory store.
        
        Args:
            store: LangGraph store instance (InMemoryStore or DB-backed)
            user_id: Identifier for this agent instance
        """
        self.user_id = user_id
        self.store = store or InMemoryStore()
        logger.info(f"✅ Initialized AgentMemoryStore for user: {user_id}")
    
    # ================ USER PREFERENCES ================
    
    def save_user_preference(self, key: str, value: Any) -> None:
        """Save a user preference (e.g., best_posting_time, preferred_topics)."""
        namespace = (*NAMESPACE_USER_PREFS, self.user_id)
        self.store.put(namespace, key, {
            "value": value,
            "updated_at": datetime.now().isoformat()
        })
        logger.info(f"💾 Saved user preference: {key} = {value}")
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        namespace = (*NAMESPACE_USER_PREFS, self.user_id)
        item = self.store.get(namespace, key)
        if item and item.value:
            return item.value.get("value", default)
        return default
    
    def get_all_user_preferences(self) -> Dict[str, Any]:
        """Get all user preferences."""
        namespace = (*NAMESPACE_USER_PREFS, self.user_id)
        items = self.store.search(namespace)
        return {
            item.key: item.value.get("value")
            for item in items
            if item.value
        }
    
    # ================ CONTENT PERFORMANCE ================
    
    def record_post_performance(
        self,
        topic: str,
        platform: str,
        engagement: int = 0,
        success: bool = True,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record post performance for learning.
        
        Args:
            topic: Post topic (e.g., "AI automation", "crypto trading")
            platform: Social platform (twitter, linkedin, etc.)
            engagement: Engagement score (likes, comments, shares)
            success: Whether post was successful
            metadata: Additional context (products mentioned, hashtags, etc.)
        """
        post_id = f"{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        namespace = (*NAMESPACE_CONTENT_PERF, self.user_id, platform)
        
        data = {
            "topic": topic,
            "platform": platform,
            "engagement": engagement,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        self.store.put(namespace, post_id, data)
        logger.info(f"📊 Recorded post performance: {topic} on {platform} (success={success})")
    
    def get_successful_topics(self, platform: Optional[str] = None, limit: int = 10) -> List[str]:
        """Get list of successful topics."""
        if platform:
            namespace = (*NAMESPACE_CONTENT_PERF, self.user_id, platform)
        else:
            namespace = (*NAMESPACE_CONTENT_PERF, self.user_id)
        
        # Search for successful posts
        items = self.store.search(namespace, filter={"success": True})
        
        # Extract unique topics, sorted by engagement
        topics_with_engagement = []
        for item in items:
            if item.value:
                topics_with_engagement.append((
                    item.value.get("topic"),
                    item.value.get("engagement", 0)
                ))
        
        # Sort by engagement and deduplicate
        topics_with_engagement.sort(key=lambda x: x[1], reverse=True)
        unique_topics = []
        seen = set()
        for topic, _ in topics_with_engagement:
            if topic and topic not in seen:
                unique_topics.append(topic)
                seen.add(topic)
                if len(unique_topics) >= limit:
                    break
        
        return unique_topics
    
    def get_platform_best_practices(self, platform: str) -> Dict[str, Any]:
        """Get learned best practices for a platform."""
        namespace = (*NAMESPACE_CONTENT_PERF, self.user_id, platform)
        items = self.store.search(namespace, filter={"success": True})
        
        # Analyze successful posts to extract patterns
        total_posts = len(items)
        if total_posts == 0:
            return {"message": f"No data yet for {platform}"}
        
        topics_count = {}
        total_engagement = 0
        best_post = None
        max_engagement = 0
        
        for item in items:
            if item.value:
                topic = item.value.get("topic")
                engagement = item.value.get("engagement", 0)
                
                topics_count[topic] = topics_count.get(topic, 0) + 1
                total_engagement += engagement
                
                if engagement > max_engagement:
                    max_engagement = engagement
                    best_post = item.value
        
        # Find most successful topic
        top_topic = max(topics_count, key=topics_count.get) if topics_count else None
        
        return {
            "platform": platform,
            "total_successful_posts": total_posts,
            "avg_engagement": total_engagement / total_posts if total_posts else 0,
            "top_topic": top_topic,
            "top_topic_count": topics_count.get(top_topic, 0) if top_topic else 0,
            "best_post": best_post,
            "max_engagement": max_engagement
        }
    
    # ================ PRODUCT MENTIONS ================
    
    def record_product_mention(
        self,
        product_name: str,
        platform: str,
        engagement: int = 0,
        conversion: bool = False
    ) -> None:
        """Record when a product is mentioned and its performance."""
        namespace = (*NAMESPACE_PRODUCTS, self.user_id)
        
        # Get existing product data or create new
        existing = self.store.get(namespace, product_name)
        if existing and existing.value:
            data = existing.value
            data["mention_count"] = data.get("mention_count", 0) + 1
            data["total_engagement"] = data.get("total_engagement", 0) + engagement
            data["conversions"] = data.get("conversions", 0) + (1 if conversion else 0)
            data["platforms"] = data.get("platforms", [])
            if platform not in data["platforms"]:
                data["platforms"].append(platform)
        else:
            data = {
                "product_name": product_name,
                "mention_count": 1,
                "total_engagement": engagement,
                "conversions": 1 if conversion else 0,
                "platforms": [platform],
                "first_mentioned": datetime.now().isoformat()
            }
        
        data["last_mentioned"] = datetime.now().isoformat()
        self.store.put(namespace, product_name, data)
        logger.info(f"📦 Recorded product mention: {product_name} on {platform}")
    
    def get_top_products(self, limit: int = 5) -> List[Dict]:
        """Get top performing products by engagement."""
        namespace = (*NAMESPACE_PRODUCTS, self.user_id)
        items = self.store.search(namespace)
        
        products = []
        for item in items:
            if item.value:
                products.append(item.value)
        
        # Sort by total engagement
        products.sort(key=lambda x: x.get("total_engagement", 0), reverse=True)
        return products[:limit]
    
    # ================ CRYPTO INSIGHTS ================
    
    def record_crypto_insight(
        self,
        token_symbol: str,
        insight_type: str,  # e.g., "high_trade_score", "successful_prediction"
        data: Dict[str, Any]
    ) -> None:
        """Record crypto trading insights."""
        namespace = (*NAMESPACE_CRYPTO, self.user_id, token_symbol)
        insight_id = f"{insight_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        insight_data = {
            "token": token_symbol,
            "type": insight_type,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        
        self.store.put(namespace, insight_id, insight_data)
        logger.info(f"💰 Recorded crypto insight: {token_symbol} - {insight_type}")
    
    def get_crypto_insights(self, token_symbol: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get crypto insights, optionally filtered by token."""
        if token_symbol:
            namespace = (*NAMESPACE_CRYPTO, self.user_id, token_symbol)
        else:
            namespace = (*NAMESPACE_CRYPTO, self.user_id)
        
        items = self.store.search(namespace)
        insights = [item.value for item in items if item.value]
        insights.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return insights[:limit]
    
    # ================ GENERAL MEMORY ================
    
    def save_memory(self, key: str, value: Any, namespace: Optional[Tuple[str, ...]] = None) -> None:
        """Save arbitrary memory with optional custom namespace."""
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)
        self.store.put(ns, key, {
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"💾 Saved memory: {key}")
    
    def get_memory(self, key: str, namespace: Optional[Tuple[str, ...]] = None, default: Any = None) -> Any:
        """Get memory by key."""
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)
        item = self.store.get(ns, key)
        if item and item.value:
            return item.value.get("value", default)
        return default
    
    def search_memory(
        self,
        query: Optional[str] = None,
        filter_dict: Optional[Dict] = None,
        namespace: Optional[Tuple[str, ...]] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Search memory with optional semantic query and filters."""
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)
        
        # LangGraph store.search supports both query (semantic) and filter (exact match)
        items = self.store.search(ns, query=query, filter=filter_dict)
        
        results = []
        for item in items:
            if item.value:
                results.append({
                    "key": item.key,
                    "value": item.value,
                    "namespace": item.namespace
                })
                if len(results) >= limit:
                    break
        
        return results
    
    # ================ MIGRATION FROM OLD MEMORY ================
    
    def migrate_from_json(self, json_path: Path) -> None:
        """Migrate data from old agent_memory.json file."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                old_memory = json.load(f)
            
            logger.info("🔄 Migrating memory from JSON file...")
            
            # Migrate successful topics
            for topic in old_memory.get("successful_topics", []):
                self.record_post_performance(
                    topic=topic,
                    platform="unknown",
                    success=True,
                    metadata={"migrated": True}
                )
            
            # Migrate product mentions
            for product, count in old_memory.get("product_mentions", {}).items():
                for _ in range(count):
                    self.record_product_mention(
                        product_name=product,
                        platform="unknown",
                        engagement=0
                    )
            
            # Migrate best posting times
            if old_memory.get("best_posting_times"):
                self.save_user_preference(
                    "best_posting_times",
                    old_memory["best_posting_times"]
                )
            
            # Migrate high engagement posts
            for post in old_memory.get("high_engagement_posts", []):
                self.record_post_performance(
                    topic=post.get("topic", "unknown"),
                    platform=post.get("platform", "unknown"),
                    engagement=post.get("engagement", 0),
                    success=True,
                    metadata={"migrated": True, "timestamp": post.get("timestamp")}
                )
            
            logger.info("✅ Migration complete!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")


# Singleton instance
_memory_store: Optional[AgentMemoryStore] = None


def get_memory_store(user_id: str = "fdwa_agent") -> AgentMemoryStore:
    """Get or create the global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = AgentMemoryStore(user_id=user_id)
    return _memory_store


def initialize_memory_store(store: BaseStore, user_id: str = "fdwa_agent") -> AgentMemoryStore:
    """Initialize memory store with a specific LangGraph store (for production use)."""
    global _memory_store
    _memory_store = AgentMemoryStore(store=store, user_id=user_id)
    return _memory_store
