"""AI Decision Engine - Makes smart content decisions based on ALL available data.

This module acts as the "brain" that consults:
1. Google Sheets (recent posts, engagement, crypto tokens)
2. Products Catalog (150+ products organized by category)
3. Knowledge Base (writing guidelines, voice/tone)
4. Business Profile (current offerings, links, CTAs)
5. Memory (past successful posts, failed attempts)

The engine decides:
- What topic to focus on?
- Which products to feature?
- What CTA to use?
- Platform-specific messaging strategy
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.agent.memory_store import get_memory_store

logger = logging.getLogger(__name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent
BUSINESS_PROFILE_PATH = BASE_DIR / "business_profile.json"
KNOWLEDGE_BASE_PATH = BASE_DIR / "FDWA_KNOWLEDGE_BASE.md"
PRODUCTS_CATALOG_PATH = BASE_DIR / "FDWA_PRODUCTS_CATALOG.md"
MEMORY_PATH = BASE_DIR / "agent_memory.json"


class AIDecisionEngine:
    """Smart AI decision-making system that uses ALL available data."""
    
    def __init__(self, use_memory_store: bool = True):
        """Initialize the decision engine.
        
        Args:
            use_memory_store: Use LangGraph memory store (recommended) vs JSON file
        """
        self.use_memory_store = use_memory_store
        self.business_profile = self._load_business_profile()
        self.products_catalog = self._load_products_catalog()
        self.knowledge_base = self._load_knowledge_base()
        
        # Use modern memory store or fallback to JSON
        if use_memory_store:
            self.memory_store = get_memory_store()
            logger.info("✅ Using LangGraph memory store")
        else:
            self.memory = self._load_memory()
            logger.info("⚠️ Using legacy JSON memory")
        
    def _load_business_profile(self) -> Dict:
        """Load business profile with products, links, CTAs."""
        try:
            with open(BUSINESS_PROFILE_PATH, encoding='utf-8') as f:
                profile = json.load(f)
                logger.info("✅ Loaded business profile: %d products", len(profile.get("products", [])))
                return profile
        except Exception as e:
            logger.warning("Could not load business profile: %s", e)
            return {}
    
    def _load_products_catalog(self) -> Dict:
        """Load full products catalog (150+ products)."""
        try:
            with open(PRODUCTS_CATALOG_PATH, encoding='utf-8') as f:
                content = f.read()
                # Parse markdown into structured data
                products = self._parse_products_markdown(content)
                logger.info("✅ Loaded products catalog: %d products", len(products))
                return {"raw": content, "products": products}
        except Exception as e:
            logger.warning("Could not load products catalog: %s", e)
            return {"raw": "", "products": []}
    
    def _parse_products_markdown(self, markdown: str) -> List[Dict]:
        """Extract products from markdown catalog."""
        products = []
        lines = markdown.split('\n')
        current_category = ""
        
        for line in lines:
            # Detect category headers
            if line.startswith('### ') and '(' in line:
                current_category = line.replace('###', '').strip()
            
            # Parse product lines (look for | Product | Price | ...)
            if '|' in line and '$' in line and not line.startswith('|---'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    product = {
                        "name": parts[1],
                        "price": parts[2],
                        "category": current_category,
                        "line": line
                    }
                    products.append(product)
        
        return products
    
    def _load_knowledge_base(self) -> str:
        """Load FDWA knowledge base with writing guidelines."""
        try:
            with open(KNOWLEDGE_BASE_PATH, encoding='utf-8') as f:
                content = f.read()
                logger.info("✅ Loaded knowledge base: %d chars", len(content))
                return content
        except Exception as e:
            logger.warning("Could not load knowledge base: %s", e)
            return ""
    
    def _load_memory(self) -> Dict:
        """Load agent memory (successful posts, engagement, lessons learned)."""
        try:
            with open(MEMORY_PATH, encoding='utf-8') as f:
                memory = json.load(f)
                logger.info("✅ Loaded memory: %d entries", len(memory.get("successful_posts", [])))
                return memory
        except FileNotFoundError:
            # Initialize empty memory structure
            logger.info("Creating new memory file...")
            memory = {
                "successful_topics": [],
                "high_engagement_posts": [],
                "product_mentions": {},
                "best_posting_times": {},
                "failed_attempts": [],
                "last_updated": datetime.now().isoformat()
            }
            self._save_memory(memory)
            return memory
        except Exception as e:
            logger.warning("Could not load memory: %s", e)
            return {}
    
    def _save_memory(self, memory: Dict):
        """Save memory to disk."""
        try:
            memory["last_updated"] = datetime.now().isoformat()
            with open(MEMORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            logger.error("Could not save memory: %s", e)
    
    def get_recent_posts_from_sheets(self, days_back: int = 7) -> List[Dict]:
        """Query Google Sheets for recent posts and engagement data."""
        try:
            from src.agent.sheets_agent import search_posts_in_sheets
            posts = search_posts_in_sheets(platform=None, days_back=days_back)
            logger.info("📊 Found %d recent posts in Google Sheets", len(posts))
            return posts
        except Exception as e:
            logger.warning("Could not fetch from Google Sheets: %s", e)
            return []
    
    def _normalize_product(self, product: Dict) -> Dict:
        """Normalize product shape across business_profile (structured) and markdown catalog."""
        if "title" in product:
            return {
                "name": product.get("title", ""),
                "price": product.get("price", 0),
                "type": product.get("type", ""),
                "channel": product.get("channel", ""),
                "url": product.get("url", ""),
                "tags": product.get("tags", []),
                "category": ", ".join(product.get("tags", [])),
            }
        return {
            "name": product.get("name", ""),
            "price": product.get("price", "$0"),
            "type": "",
            "channel": "gumroad",
            "url": "https://futuristicwealth.gumroad.com/",
            "tags": [],
            "category": product.get("category", ""),
        }

    def _price_value(self, price) -> float:
        """Coerce price (int/float/str) → float."""
        if isinstance(price, (int, float)):
            return float(price)
        s = str(price).replace("$", "").replace("+", "").strip().split()[0] if price else "0"
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def score_for_revenue(self, product: Dict, topic: str) -> float:
        """CFO-style revenue score: weight by price, tags, recency, lead-magnet potential.

        Higher score = better revenue/funnel candidate for the topic.
        """
        score = 0.0
        topic_lower = topic.lower()
        name_lower = product.get("name", "").lower()
        tags = [t.lower() for t in product.get("tags", [])]
        category_lower = product.get("category", "").lower()

        for kw in topic_lower.split():
            if not kw or len(kw) < 3:
                continue
            if kw in name_lower:
                score += 12
            if kw in category_lower:
                score += 8
            if any(kw in t for t in tags):
                score += 10

        price = self._price_value(product.get("price"))
        if price == 0.0:
            score += 8
        elif price < 20:
            score += 5
        elif price < 50:
            score += 4
        else:
            score += 2

        if "free_lead_magnet" in tags:
            score += 6
        if "openclaw" in tags:
            score += 4

        product_name = product.get("name", "")
        try:
            if self.use_memory_store:
                product_data = self.memory_store.get_top_products(limit=100)
                for p in product_data:
                    if p.get("product_name") == product_name:
                        score += min(p.get("mention_count", 0), 5)
                        break
            else:
                mentions = self.memory.get("product_mentions", {}).get(product_name, 0)
                score += min(mentions, 5)
        except Exception:
            pass

        return score

    def select_relevant_products(self, topic: str, category: str | None = None, limit: int = 2) -> List[Dict]:
        """Select revenue-optimal products for the topic.

        Prefers structured products from business_profile.json (with price/tags/url),
        falls back to markdown catalog. Returns normalized dicts.
        """
        bp_products = self.business_profile.get("products", [])
        if bp_products:
            products = [self._normalize_product(p) for p in bp_products]
        else:
            products = [self._normalize_product(p) for p in self.products_catalog.get("products", [])]

        if not products:
            logger.warning("No products available")
            return []

        if category:
            cat_lower = category.lower()
            products = [
                p for p in products
                if cat_lower in p["category"].lower() or any(cat_lower in t for t in p["tags"])
            ]

        scored = [(self.score_for_revenue(p, topic), p) for p in products]
        scored.sort(reverse=True, key=lambda x: x[0])
        selected = [p for _, p in scored[:limit]]

        logger.info("🎯 Selected %d products for topic '%s': %s",
                   len(selected), topic, [p["name"][:50] for p in selected])
        return selected

    def cfo_pick_strategy(self, topic: str, products: List[Dict] | None = None) -> Dict:
        """CFO funnel pick: free lead magnet + paid upsell + framework angle + CTA.

        Returns:
            {
              "free_guide": {...} or None,  # the lead magnet
              "paid_skill": {...} or None,  # the upsell
              "framework_used": ["LangChain", "LangGraph", "Composio"],
              "primary_url": str,
              "cta_line": str,
              "affiliate": {...} or None    # contextual affiliate offer
            }
        """
        if products is None:
            products = self.select_relevant_products(topic, limit=4)

        free_guide = None
        paid_skill = None
        for p in products:
            price = self._price_value(p.get("price"))
            if price == 0.0 and free_guide is None:
                free_guide = p
            elif price > 0 and paid_skill is None:
                paid_skill = p
            if free_guide and paid_skill:
                break

        # If we only got free products, scan whole catalog for best paid upsell
        if paid_skill is None:
            all_normalized = [self._normalize_product(p) for p in self.business_profile.get("products", [])]
            paid_candidates = [p for p in all_normalized if self._price_value(p.get("price")) > 0]
            if paid_candidates:
                scored = [(self.score_for_revenue(p, topic), p) for p in paid_candidates]
                scored.sort(reverse=True, key=lambda x: x[0])
                paid_skill = scored[0][1]

        # Same for free guide
        if free_guide is None:
            all_normalized = [self._normalize_product(p) for p in self.business_profile.get("products", [])]
            free_candidates = [p for p in all_normalized if self._price_value(p.get("price")) == 0.0]
            if free_candidates:
                scored = [(self.score_for_revenue(p, topic), p) for p in free_candidates]
                scored.sort(reverse=True, key=lambda x: x[0])
                free_guide = scored[0][1]

        frameworks = self.business_profile.get("frameworks_we_use_and_tag", [])
        topic_lower = topic.lower()
        relevant_frameworks = []
        if any(kw in topic_lower for kw in ["agent", "openclaw", "ai", "automation", "build", "skill"]):
            relevant_frameworks = ["LangChain", "LangGraph", "Composio"]
        elif "crypto" in topic_lower or "trading" in topic_lower:
            relevant_frameworks = ["LangChain", "Composio", "Mistral"]
        elif "credit" in topic_lower or "real estate" in topic_lower:
            relevant_frameworks = ["LangChain", "Composio"]
        else:
            relevant_frameworks = frameworks[:3]

        affiliate = None
        for offer in self.business_profile.get("affiliate_offers", []):
            offer_topic = offer.get("topic", "").lower().replace("_", " ")
            if any(t in topic_lower for t in offer_topic.split()):
                affiliate = offer
                break

        primary = free_guide or paid_skill
        primary_url = (primary or {}).get("url", "https://futuristicwealth.gumroad.com/")

        if free_guide and paid_skill:
            cta_line = (
                f"Free starter: {free_guide['name']} → {free_guide['url']} "
                f"| Upgrade: {paid_skill['name']} (${self._price_value(paid_skill['price'])}) → {paid_skill['url']}"
            )
        elif free_guide:
            cta_line = f"Grab the free guide: {free_guide['name']} → {free_guide['url']}"
        elif paid_skill:
            cta_line = f"Get the skill: {paid_skill['name']} (${self._price_value(paid_skill['price'])}) → {paid_skill['url']}"
        else:
            cta_line = "Browse our OpenClaw skills: https://futuristicwealth.gumroad.com/"

        return {
            "free_guide": free_guide,
            "paid_skill": paid_skill,
            "framework_used": relevant_frameworks,
            "primary_url": primary_url,
            "cta_line": cta_line,
            "affiliate": affiliate,
        }
    
    def get_content_strategy(self, trend_data: str) -> Dict:
        """Generate comprehensive content strategy based on ALL available data.
        
        This is the MAIN intelligence function that decides:
        1. What topic to focus on
        2. Which products to feature
        3. What CTA to use
        4. Platform-specific messaging
        
        Args:
            trend_data: Trending topic from research
            
        Returns:
            Strategy dict with topic, products, CTAs, platform_guidance
        """
        logger.info("🧠 AI DECISION ENGINE: Analyzing all data sources...")
        
        # 1. Analyze recent posts to avoid duplicates and find patterns
        recent_posts = self.get_recent_posts_from_sheets(days_back=7)
        recent_topics = self._extract_topics_from_posts(recent_posts)
        
        logger.info("📊 Recent topics (last 7 days): %s", recent_topics[:5])
        
        # 2. Determine primary topic from trend data
        primary_topic = self._determine_topic(trend_data, recent_topics)
        
        # 3. Select relevant products (avoid over-promoting same products)
        products_to_feature = self.select_relevant_products(
            topic=primary_topic,
            limit=2
        )
        
        # 4. Choose best CTA based on topic
        cta = self._select_cta(primary_topic)
        
        # 5. Platform-specific guidance
        platform_guidance = self._get_platform_guidance(primary_topic, products_to_feature)
        
        # 6. Memory insights
        memory_insights = self._get_memory_insights(primary_topic)

        # 7. Memory examples (top historical posts + semantic matches) to surface for LLM prompts
        memory_examples = []
        try:
            if self.use_memory_store:
                # Top posts by engagement
                memory_examples = self.memory_store.get_top_posts(limit=3)

                # Add semantic matches (RAG-style) from memory_vectors for the current trend/topic
                try:
                    semantic_matches = self.memory_store.search_memory(query=trend_data, limit=3)
                    # prefer semantic matches first
                    if semantic_matches:
                        # convert results to same shape as get_top_posts returns
                        mem_sem = []
                        for m in semantic_matches:
                            v = m.get("value")
                            # value may already be dict-like
                            if isinstance(v, dict):
                                mem_sem.append(v)
                            else:
                                mem_sem.append({"topic": primary_topic, "platform": "memory", "engagement": 0, "meta": v})
                        # prepend semantic matches
                        memory_examples = mem_sem + memory_examples
                        memory_examples = memory_examples[:3]
                except Exception:
                    pass
            else:
                # Legacy JSON: attempt to extract high_engagement_posts
                memory_examples = self.memory.get("high_engagement_posts", [])[:3]
        except Exception:
            memory_examples = []
        
        # 7b. CFO monetization angle (free guide → paid upsell + framework tagging)
        monetization_angle = self.cfo_pick_strategy(primary_topic, products_to_feature)

        strategy = {
            "topic": primary_topic,
            "products": products_to_feature,
            "cta": cta,
            "platform_guidance": platform_guidance,
            "memory_insights": memory_insights,
            "memory_examples": memory_examples,
            "recent_topics": recent_topics,
            "monetization_angle": monetization_angle,
            "decision_timestamp": datetime.now().isoformat()
        }
        
        logger.info("✅ STRATEGY DECIDED:")
        logger.info("   Topic: %s", primary_topic)
        logger.info("   Products: %s", [p["name"][:40] for p in products_to_feature])
        logger.info("   CTA: %s", cta[:60])
        
        return strategy
    
    def _extract_topics_from_posts(self, posts: List[Dict]) -> List[str]:
        """Extract topics from recent posts."""
        topics = []
        for post in posts:
            content = post.get("content", "").lower()
            # Simple keyword extraction
            if "ai" in content or "automation" in content:
                topics.append("AI automation")
            elif "credit" in content or "debt" in content:
                topics.append("credit repair")
            elif "real estate" in content or "land" in content:
                topics.append("real estate")
            elif "crypto" in content or "bitcoin" in content:
                topics.append("cryptocurrency")
            elif "business" in content or "entrepreneur" in content:
                topics.append("business growth")
        return topics
    
    def _determine_topic(self, trend_data: str, recent_topics: List[str]) -> str:
        """Determine primary topic, avoiding over-used topics."""
        trend_lower = trend_data.lower()
        
        # Topic detection with variety logic
        possible_topics = []
        
        if "ai" in trend_lower or "automation" in trend_lower:
            possible_topics.append("AI automation")
        if "credit" in trend_lower or "debt" in trend_lower or "financial" in trend_lower:
            possible_topics.append("credit repair")
        if "business" in trend_lower or "entrepreneur" in trend_lower:
            possible_topics.append("business growth")
        if "crypto" in trend_lower or "bitcoin" in trend_lower:
            possible_topics.append("cryptocurrency")
        if "real estate" in trend_lower or "property" in trend_lower:
            possible_topics.append("real estate")
        
        # === MEMORY BIAS: prefer historically successful topics when appropriate ===
        try:
            if self.use_memory_store:
                mem_topics = self.memory_store.get_successful_topics(limit=10)
            else:
                mem_topics = self.memory.get("successful_topics", [])

            for mem_topic in mem_topics:
                for candidate in possible_topics:
                    if mem_topic and candidate and mem_topic.lower() == candidate.lower():
                        # Prefer memory-backed candidate if it hasn't been over-used recently
                        if recent_topics.count(candidate) < 2:
                            return candidate
        except Exception:
            # If memory check fails, continue with standard logic
            pass

        # Avoid recently used topics
        for topic in possible_topics:
            if recent_topics.count(topic) < 2:  # Max 2 uses in last 7 days
                return topic
        
        # Fallback: return first possible or default
        return possible_topics[0] if possible_topics else "AI automation"
    
    def _select_cta(self, topic: str) -> str:
        """Select most relevant CTA based on topic."""
        ctas = {
            "AI automation": "📅 Book a free AI consultation: https://cal.com/bookme-daniel/ai-consultation-smb",
            "credit repair": "📅 Get a free credit analysis: https://cal.com/bookme-daniel/credit-consultation",
            "business growth": "📅 Schedule a strategy session: https://cal.com/bookme-daniel/business-consultation",
            "cryptocurrency": "💰 Learn more: https://fdwa.site",
            "real estate": "🏠 Book consultation: https://cal.com/bookme-daniel/real-estate-consultation"
        }
        
        return ctas.get(topic, "🌐 Visit: https://fdwa.site")
    
    def _get_platform_guidance(self, topic: str, products: List[Dict]) -> Dict:
        """Provide platform-specific content guidance."""
        return {
            "twitter": {
                "style": "Short, punchy, 1-2 hashtags",
                "product_mention": "Brief mention with price" if products else None,
                "char_limit": 280
            },
            "linkedin": {
                "style": "Professional, business benefits-focused",
                "product_mention": "Full pitch with ROI/benefits" if products else None,
                "char_limit": 3000
            },
            "facebook": {
                "style": "Conversational, storytelling",
                "product_mention": "Casual mention with testimonial" if products else None,
                "char_limit": 5000
            },
            "instagram": {
                "style": "Visual, emoji-heavy, inspiring",
                "product_mention": "Link in bio approach" if products else None,
                "char_limit": 2200
            },
            "telegram": {
                "style": "Internal status briefing — what we researched, posted, promoted, next run",
                "product_mention": "Mention which product the run promoted" if products else None,
                "char_limit": 4096
            }
        }
    
    def _get_memory_insights(self, topic: str) -> str:
        """Get relevant insights from past performance."""
        insights = []
        
        if self.use_memory_store:
            # Use modern memory store
            successful_topics = self.memory_store.get_successful_topics(limit=20)
            if topic in successful_topics:
                insights.append(f"✅ Topic '{topic}' performed well in past")
            
            best_times = self.memory_store.get_user_preference("best_posting_times")
            if best_times:
                insights.append(f"⏰ Best times: {best_times}")
            
            failed = self.memory_store.get_user_preference("failed_attempts", [])
            if failed:
                insights.append(f"⚠️ Avoid: {', '.join(failed[-3:])}")
        else:
            # Legacy JSON memory
            if topic in self.memory.get("successful_topics", []):
                insights.append(f"✅ Topic '{topic}' performed well in past")
            
            best_times = self.memory.get("best_posting_times", {})
            if best_times:
                insights.append(f"⏰ Best times: {best_times}")
            
            failed = self.memory.get("failed_attempts", [])
            if failed:
                insights.append(f"⚠️ Avoid: {', '.join(failed[-3:])}")
        
        return " | ".join(insights) if insights else "No historical data yet"
    
    def record_post_outcome(self, topic: str, products: List[str], platform: str, 
                           engagement: int | None = None, success: bool = True):
        """Record post outcome to improve future decisions."""
        try:
            if self.use_memory_store:
                # Use modern memory store
                self.memory_store.record_post_performance(
                    topic=topic,
                    platform=platform,
                    engagement=engagement or 0,
                    success=success,
                    metadata={"products": products}
                )
                
                # Track product mentions
                for product in products:
                    self.memory_store.record_product_mention(
                        product_name=product,
                        platform=platform,
                        engagement=engagement or 0,
                        conversion=False  # Would need conversion tracking
                    )
                
                logger.info("💾 Recorded post outcome (memory store): topic=%s, success=%s", topic, success)
            else:
                # Legacy JSON memory
                memory = self._load_memory()
                
                if success:
                    # Track successful topic
                    if topic not in memory["successful_topics"]:
                        memory["successful_topics"].append(topic)
                    
                    # Track product mentions
                    for product in products:
                        if product in memory["product_mentions"]:
                            memory["product_mentions"][product] += 1
                        else:
                            memory["product_mentions"][product] = 1
                    
                    # Track engagement if provided
                    if engagement:
                        if "high_engagement_posts" not in memory:
                            memory["high_engagement_posts"] = []
                        memory["high_engagement_posts"].append({
                            "topic": topic,
                            "platform": platform,
                            "engagement": engagement,
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    # Track failed attempts
                    if "failed_attempts" not in memory:
                        memory["failed_attempts"] = []
                    memory["failed_attempts"].append(topic)
                
                self._save_memory(memory)
                logger.info("💾 Recorded post outcome (JSON): topic=%s, success=%s", topic, success)
            
        except Exception as e:
            logger.error("Could not record outcome: %s", e)


# Singleton instance
_decision_engine = None

def get_decision_engine() -> AIDecisionEngine:
    """Get the global AI decision engine instance."""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = AIDecisionEngine()
    return _decision_engine
