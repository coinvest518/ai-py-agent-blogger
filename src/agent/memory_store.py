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
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

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

# Default Astra collection for untyped/general writes.
# Each logical domain now uses its own collection (see ASTRA_COLLECTIONS).
ASTRA_COLLECTION = os.getenv("ASTRA_COLLECTION_NAME", "ai_auto")

# Per-type collection routing — keeps memory segmented instead of one dumping ground.
# Override any of these via env if you want different names in Astra.
ASTRA_COLLECTIONS: Dict[str, str] = {
    "content_performance": os.getenv("ASTRA_COLL_CONTENT", "fdwa_content_performance"),
    "products": os.getenv("ASTRA_COLL_PRODUCTS", "fdwa_products"),
    "crypto_insights": os.getenv("ASTRA_COLL_CRYPTO", "fdwa_crypto_insights"),
    "general_memory": os.getenv("ASTRA_COLL_GENERAL", "fdwa_general_memory"),
    "engagement_snapshot": os.getenv("ASTRA_COLL_ENGAGEMENT", "fdwa_engagement"),
    "supervisor_reflection": os.getenv("ASTRA_COLL_REFLECTION", "fdwa_reflections"),
}


def _astra_env() -> tuple[str | None, str | None, str]:
    """Resolve Astra endpoint + token from env, supporting both naming styles."""
    endpoint = os.getenv("ASTRA_DB_API_ENDPOINT") or os.getenv("ASTRA_DB_ENDPOINT")
    token = (
        os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        or os.getenv("ASTRA_APPLICATION_TOKEN")
        or os.getenv("ASTRA_DB_API_KEY")
    )
    keyspace = os.getenv("ASTRA_DB_KEYSPACE") or os.getenv("ASTRA_KEYSPACE", "default_keyspace")
    return endpoint, token, keyspace


class AgentMemoryStore:
    """Manages long-term memory for the AI agent using LangGraph store.

    Optional: when Astra DB environment variables are present, memory will also be
    persisted to an Astra DB Serverless (vector/collection) database using the
    DataStax `astrapy` client. The Astra integration is best-effort and falls
    back to the in-memory LangGraph store if unavailable.
    """
    
    def __init__(self, store: BaseStore | None = None, user_id: str = "fdwa_agent"):
        """Initialize memory store.
        
        Args:
            store: LangGraph store instance (InMemoryStore or DB-backed)
            user_id: Identifier for this agent instance
        """
        import os

        self.user_id = user_id
        self.store = store or InMemoryStore()
        self._astra_db = None
        self._astra_ready_collections: set[str] = set()
        self._astra_failed_until: Dict[str, float] = {}

        # Detect Astra configuration via environment variables (best-effort)
        astra_endpoint, astra_token, astra_keyspace = _astra_env()

        if astra_endpoint and astra_token:
            try:
                from astrapy import DataAPIClient

                client = DataAPIClient()
                self._astra_db = client.get_database(astra_endpoint, token=astra_token)
                self._astra_keyspace = astra_keyspace
                logger.info("✅ Connected to Astra DB (endpoint detected)")
            except Exception as e:
                self._astra_db = None
                logger.warning("⚠️ Astra DB init failed (will continue without Astra): %s", e)
        else:
            logger.debug("Astra DB not configured (no ASTRA_* env vars)")

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
        metadata: Dict | None = None
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

        # Persist to Astra DB (best-effort)
        try:
            astra_doc = {
                "_id": post_id,
                "_type": "content_performance",
                "user_id": self.user_id,
                **data
            }
            self._astra_insert(astra_doc)
        except Exception:
            pass
    
    def get_successful_topics(self, platform: str | None = None, limit: int = 10) -> List[str]:
        """Get list of successful topics.

        Prefer reading from Astra if configured, otherwise use LangGraph store.
        """
        # Use Astra if available for durable insights
        if self._astra_db:
            try:
                query = {"_type": "content_performance", "success": True}
                if platform:
                    query["platform"] = platform
                rows = self._astra_find(filter_dict=query, limit=limit * 5)
                # Sort and dedupe by engagement
                rows.sort(key=lambda r: r.get("engagement", 0), reverse=True)
                unique_topics = []
                seen = set()
                for r in rows:
                    t = r.get("topic")
                    if t and t not in seen:
                        unique_topics.append(t)
                        seen.add(t)
                    if len(unique_topics) >= limit:
                        break
                return unique_topics
            except Exception:
                # fallback to local store on error
                pass

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

        # Persist to Astra DB (best-effort)
        try:
            astra_doc = {
                "_id": product_name,
                "_type": "products",
                "user_id": self.user_id,
                **data
            }
            self._astra_insert(astra_doc)
        except Exception:
            pass
    
    def get_top_products(self, limit: int = 5) -> List[Dict]:
        """Get top performing products by engagement.

        Prefer durable Astra collection when available.
        """
        if self._astra_db:
            try:
                rows = self._astra_find(filter_dict={"_type": "products"}, limit=limit * 5)
                products = [r for r in rows if r]
                products.sort(key=lambda x: x.get("total_engagement", 0), reverse=True)
                return products[:limit]
            except Exception:
                pass

        namespace = (*NAMESPACE_PRODUCTS, self.user_id)
        items = self.store.search(namespace)
        
        products = []
        for item in items:
            if item.value:
                products.append(item.value)
        
        # Sort by total engagement
        products.sort(key=lambda x: x.get("total_engagement", 0), reverse=True)
        return products[:limit]
    def get_top_posts(self, platform: str | None = None, limit: int = 5) -> List[Dict]:
        """Return top posts recorded in memory, optionally filtered by platform.

        Returns a list of post dictionaries (topic, platform, engagement, timestamp, metadata)
        sorted by engagement (descending). Will query Astra if configured.
        """
        # If Astra is configured, prefer durable store
        if self._astra_db:
            try:
                coll = self._astra_db.get_collection(ASTRA_COLLECTION)
                query = {"_type": "content_performance", "success": True}
                if platform:
                    query["platform"] = platform
                rows = coll.find(filter=query, limit=limit * 5)
                posts = [r for r in rows]
                posts.sort(key=lambda p: (p.get("engagement", 0), p.get("timestamp", "")), reverse=True)
                # dedupe by topic and return top `limit`
                seen = set()
                out = []
                for p in posts:
                    topic = p.get("topic")
                    if topic and topic not in seen:
                        seen.add(topic)
                        out.append(p)
                    if len(out) >= limit:
                        break
                return out
            except Exception:
                # fallback to in-memory store if Astra query fails
                pass

        if platform:
            namespace = (*NAMESPACE_CONTENT_PERF, self.user_id, platform)
        else:
            namespace = (*NAMESPACE_CONTENT_PERF, self.user_id)

        items = self.store.search(namespace)
        posts = [item.value for item in items if item.value]

        # Sort by engagement, fallback to timestamp if engagement missing
        def _sort_key(p):
            return (p.get("engagement", 0), p.get("timestamp", ""))

        posts.sort(key=_sort_key, reverse=True)
        return posts[:limit]

    # ------------------ Astra helpers (best-effort persistence) ------------------
    # Each logical domain gets its own collection (see ASTRA_COLLECTIONS).
    # Callers pass a `doc_type` that maps to a collection name.

    def _collection_name(self, doc_type: str | None) -> str:
        if doc_type and doc_type in ASTRA_COLLECTIONS:
            return ASTRA_COLLECTIONS[doc_type]
        return ASTRA_COLLECTION

    def _astra_ensure_collection(self, name: str) -> bool:
        """Ensure a specific Astra collection exists (create if missing)."""
        if not self._astra_db:
            return False
        if name in self._astra_ready_collections:
            return True
        if self._astra_failed_until.get(name, 0) > time.time():
            return False
        try:
            coll = self._astra_db.get_collection(name)
            coll.find_one({})
            self._astra_ready_collections.add(name)
            logger.info("✅ Astra collection '%s' verified", name)
            return True
        except Exception as e:
            msg = str(e)
            if "COLLECTION_NOT_EXIST" in msg or "does not exist" in msg.lower():
                if self._astra_create_collection(name):
                    self._astra_ready_collections.add(name)
                    logger.info("✅ Astra collection '%s' created", name)
                    return True
            cooldown_secs = int(os.getenv("ASTRA_COLLECTION_RETRY_COOLDOWN_SECS", "300"))
            self._astra_failed_until[name] = time.time() + cooldown_secs
            logger.debug("Astra collection '%s' not available (cooldown %ds): %s", name, cooldown_secs, e)
            return False

    def _astra_create_collection(self, name: str) -> bool:
        """Create a collection with vectorize + filterable indexing (best-effort)."""
        try:
            from astrapy.info import (
                CollectionDefinition,
                CollectionVectorOptions,
                VectorServiceOptions,
            )
            definition = CollectionDefinition(
                vector=CollectionVectorOptions(
                    service=VectorServiceOptions(
                        provider="nvidia",
                        model_name="NV-Embed-QA",
                    ),
                ),
                indexing={"allow": ["_type", "topic", "platform", "timestamp", "token_symbol"]},
            )
            self._astra_db.create_collection(name, definition=definition)
            return True
        except Exception as e:
            logger.warning("Astra create_collection('%s') failed: %s", name, e)
            try:
                self._astra_db.create_collection(name)
                return True
            except Exception as e2:
                logger.debug("Astra bare create_collection('%s') also failed: %s", name, e2)
                return False

    def _astra_insert(self, doc: Dict) -> bool:
        """Insert a document into the appropriate Astra collection (by `_type`)."""
        if not self._astra_db:
            return False
        name = self._collection_name(doc.get("_type"))
        if not self._astra_ensure_collection(name):
            return False
        # Retry loop with exponential backoff to handle transient Astra errors
        max_retries = int(os.getenv("ASTRA_INSERT_MAX_RETRIES", "3"))
        backoff = float(os.getenv("ASTRA_INSERT_BACKOFF_SECS", "1"))
        attempt = 0
        last_exc = None
        while attempt < max_retries:
            attempt += 1
            try:
                coll = self._astra_db.get_collection(name)
                doc_id = doc.get("_id")
                if doc_id is not None:
                    coll.replace_one({"_id": doc_id}, doc, upsert=True)
                else:
                    coll.insert_one(doc)
                return True
            except Exception as e:
                last_exc = e
                logger.debug("Astra insert attempt %d/%d into '%s' failed: %s", attempt, max_retries, name, e)
                time.sleep(backoff)
                backoff *= 2

        # If we reach here, all attempts failed — persist the failed doc locally for later retry
        try:
            base = Path(__file__).resolve().parent.parent
            failed_dir = base / "data"
            failed_dir.mkdir(parents=True, exist_ok=True)
            out_path = failed_dir / "astra_failed_inserts.jsonl"
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"collection": name, "doc": doc, "error": str(last_exc)}) + "\n")
            logger.warning("Astra insert failed after %d attempts — queued to %s", max_retries, out_path)
        except Exception as e:
            logger.debug("Failed to persist failed Astra insert locally: %s", e)
        return False

    def _astra_find(self, filter_dict: Dict | None = None, limit: int = 10, vector_query: str | None = None) -> List[Dict]:
        """Find documents by routing to the collection matching filter_dict['_type']."""
        if not self._astra_db:
            return []
        doc_type = (filter_dict or {}).get("_type")
        name = self._collection_name(doc_type)
        if not self._astra_ensure_collection(name):
            return []
        try:
            coll = self._astra_db.get_collection(name)
            if vector_query:
                rows = coll.find(filter=filter_dict or {}, sort={"$vectorize": vector_query}, limit=limit)
            else:
                rows = coll.find(filter=filter_dict or {}, limit=limit)
            return [r for r in rows]
        except Exception as e:
            logger.debug("Astra find on '%s' failed: %s", name, e)
            return []
    
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

        # Persist to Astra DB (best-effort)
        try:
            astra_doc = {
                "_id": insight_id,
                "_type": "crypto_insights",
                "user_id": self.user_id,
                "token": token_symbol,
                **insight_data
            }
            self._astra_insert(astra_doc)
        except Exception:
            pass
    
    def get_crypto_insights(self, token_symbol: str | None = None, limit: int = 10) -> List[Dict]:
        """Get crypto insights, optionally filtered by token.

        Prefer Astra if configured.
        """
        if self._astra_db:
            try:
                query = {"_type": "crypto_insights"}
                if token_symbol:
                    query["token"] = token_symbol
                rows = self._astra_find(filter_dict=query, limit=limit)
                rows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                return rows[:limit]
            except Exception:
                pass

        if token_symbol:
            namespace = (*NAMESPACE_CRYPTO, self.user_id, token_symbol)
        else:
            namespace = (*NAMESPACE_CRYPTO, self.user_id)
        
        items = self.store.search(namespace)
        insights = [item.value for item in items if item.value]
        insights.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return insights[:limit]    
    # ================ GENERAL MEMORY ================
    
    def save_memory(self, key: str, value: Any, namespace: Tuple[str, ...] | None = None) -> None:
        """Save arbitrary memory with optional custom namespace."""
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)
        self.store.put(ns, key, {
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"💾 Saved memory: {key}")

        # Persist general memory to Astra (best-effort)
        try:
            astra_doc = {
                "_id": f"{key}_{int(time.time())}",
                "_type": "general_memory",
                "user_id": self.user_id,
                "namespace": list(ns),
                "key": key,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
            self._astra_insert(astra_doc)
        except Exception:
            pass
    
    def get_memory(self, key: str, namespace: Tuple[str, ...] | None = None, default: Any = None) -> Any:
        """Get memory by key."""
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)
        item = self.store.get(ns, key)
        if item and item.value:
            return item.value.get("value", default)
        return default
    
    def search_memory(
        self,
        query: str | None = None,
        filter_dict: Dict | None = None,
        namespace: Tuple[str, ...] | None = None,
        limit: int = 10
    ) -> List[Dict]:
        """Search memory with optional semantic query and filters.

        If `query` is provided and Astra is configured, use Astra's vector search
        (server-side vectorize) against the `memory_vectors` collection as a
        semantic fallback. Otherwise, fall back to the LangGraph store search.
        """
        ns = namespace or (*NAMESPACE_GENERAL, self.user_id)

        # If a semantic query and Astra available, use vector search
        if query and self._astra_db:
            try:
                filt = {"_type": "general_memory"}
                if filter_dict:
                    filt.update(filter_dict)
                rows = self._astra_find(filter_dict=filt, limit=limit, vector_query=query)
                results = []
                for r in rows:
                    results.append({
                        "key": r.get("key"),
                        "value": r.get("meta") or r.get("content") or r.get("value"),
                        "namespace": tuple(r.get("namespace", []))
                    })
                return results
            except Exception:
                pass

        # If Astra is configured and no semantic query, try general_memory type
        if self._astra_db and not query:
            try:
                filt = {"_type": "general_memory"}
                if filter_dict:
                    filt.update(filter_dict)
                rows = self._astra_find(filter_dict=filt, limit=limit)
                results = []
                for r in rows:
                    results.append({
                        "key": r.get("key"),
                        "value": r.get("value"),
                        "namespace": tuple(r.get("namespace", []))
                    })
                return results
            except Exception:
                pass

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
            with open(json_path, encoding='utf-8') as f:
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

    def migrate_to_astra(self) -> bool:
        """Copy in-memory/LangGraph memory into the single Astra collection (best-effort).

        All documents go into ASTRA_COLLECTION with a `_type` discriminator field.
        Returns True if the migration was attempted; raises/logs on failure.
        """
        if not self._astra_db:
            logger.warning("Astra DB not configured — cannot migrate to Astra")
            return False
        try:
            logger.info("🔁 Migrating LangGraph memory into Astra collection '%s'...", ASTRA_COLLECTION)

            # Migrate content performance
            items = self.store.search((*NAMESPACE_CONTENT_PERF, self.user_id))
            for item in items:
                if item and item.value:
                    doc = {"_id": item.key, "_type": "content_performance", "user_id": self.user_id, **item.value}
                    self._astra_insert(doc)

            # Migrate products
            items = self.store.search((*NAMESPACE_PRODUCTS, self.user_id))
            for item in items:
                if item and item.value:
                    doc = {"_id": item.key, "_type": "products", "user_id": self.user_id, **item.value}
                    self._astra_insert(doc)

            # Migrate crypto insights
            items = self.store.search((*NAMESPACE_CRYPTO, self.user_id))
            for item in items:
                if item and item.value:
                    doc = {"_id": item.key, "_type": "crypto_insights", "user_id": self.user_id, **item.value}
                    self._astra_insert(doc)

            # Migrate general memories
            items = self.store.search((*NAMESPACE_GENERAL, self.user_id))
            for item in items:
                if item and item.value:
                    doc = {"_id": item.key, "_type": "general_memory", "user_id": self.user_id, **item.value}
                    self._astra_insert(doc)

            logger.info("✅ Migration to Astra complete")
            return True
        except Exception as e:
            logger.error("Migration to Astra failed: %s", e)
            return False

# Singleton instance
_memory_store: AgentMemoryStore | None = None


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


def get_astra_status() -> dict:
    """Return a summary of Astra DB health (for the dashboard)."""
    endpoint, token, keyspace = _astra_env()
    if not (endpoint and token):
        return {
            "astra": "not_configured",
            "endpoint": None,
            "keyspace": keyspace,
            "collections": list(ASTRA_COLLECTIONS.values()),
        }

    store = get_memory_store()
    ready = sorted(store._astra_ready_collections) if store._astra_db else []
    pending = [c for c in ASTRA_COLLECTIONS.values() if c not in ready]

    if store._astra_db:
        try:
            for name in ASTRA_COLLECTIONS.values():
                store._astra_ensure_collection(name)
            ready = sorted(store._astra_ready_collections)
            pending = [c for c in ASTRA_COLLECTIONS.values() if c not in ready]
        except Exception:
            pass

    return {
        "astra": "connected" if store._astra_db else "error",
        "endpoint": (endpoint[:40] + "…") if endpoint and len(endpoint) > 40 else endpoint,
        "keyspace": keyspace,
        "default_collection": ASTRA_COLLECTION,
        "collections_ready": ready,
        "collections_pending": pending,
        "routing": ASTRA_COLLECTIONS,
    }
