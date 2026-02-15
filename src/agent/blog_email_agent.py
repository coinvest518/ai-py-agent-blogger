"""Blog Email Agent for FDWA AI Automation Agency.

This agent generates blog content using predefined templates and sends it via Gmail.
Image URLs are embedded directly in the HTML body for display.
Now includes strategic knowledge base integration and link performance tracking.
"""

import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import time

import requests
from composio import Composio
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Initialize Composio client
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    toolkit_versions={
        "gmail": os.getenv("COMPOSIO_TOOLKIT_VERSION_GMAIL")
    }
)

# Pydantic model for structured blog output
class BlogPost(BaseModel):
    """Structured blog post output from LLM."""
    title: str = Field(description="Engaging title with data or specific benefit")
    html: str = Field(description="1000-1500 word detailed HTML article")
    excerpt: str = Field(description="Compelling 1-2 sentence hook")
    rationale: List[str] = Field(default_factory=list, description="Why this approach")
    products_mentioned: List[str] = Field(default_factory=list, description="FDWA products used")
    affiliate_tools_used: List[str] = Field(default_factory=list, description="Affiliate tools mentioned")
    consultation_type: str = Field(default="general", description="ai, credit, or general")
    word_count: int = Field(default=1200, description="Approximate word count")

# Configure logging
logger = logging.getLogger(__name__)

# Import link tracker for performance tracking
try:
    from .link_tracker import LinkPerformanceTracker
    link_tracker = LinkPerformanceTracker()
    logger.info("✅ Link performance tracker initialized")
except Exception as e:
    logger.warning(f"Link tracker not available: {e}")
    link_tracker = None

# File to track sent blog posts (prevents duplicates)
SENT_POSTS_FILE = Path(__file__).parent.parent.parent / "sent_blog_posts.json"


def _load_sent_posts() -> Dict[str, Any]:
    """Load the record of sent blog posts.

    New structure includes a `sent_posts` list with objects:
      { title, excerpt, snippet, topic, date }
    Backwards-compatible keys (`sent_titles`, `sent_hashes`, `last_topics`) are kept.
    """
    if SENT_POSTS_FILE.exists():
        try:
            with open(SENT_POSTS_FILE, encoding="utf-8") as f:
                data = json.load(f)

                # Ensure new keys exist for backward compatibility
                data.setdefault("sent_posts", [])
                data.setdefault("sent_titles", [p.get("title") for p in data.get("sent_posts", []) if p.get("title")])
                data.setdefault("sent_hashes", data.get("sent_hashes", []))
                data.setdefault("last_topics", data.get("last_topics", []))
                return data
        except (OSError, json.JSONDecodeError):
            pass

    return {"sent_posts": [], "sent_titles": [], "sent_hashes": [], "last_topics": []}


def _save_sent_posts(data: Dict[str, Any]) -> None:
    """Save the record of sent blog posts."""
    try:
        with open(SENT_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.error("Failed to save sent posts: %s", e)


def _get_content_hash(title: str, content: str) -> str:
    """Generate a hash for content to detect duplicates."""
    combined = f"{title.lower().strip()}:{content[:200].lower().strip()}"
    return hashlib.md5(combined.encode()).hexdigest()


def _is_duplicate_post(title: str, content: str, topic: str) -> bool:
    """Check if this post has already been sent recently."""
    sent_data = _load_sent_posts()
    content_hash = _get_content_hash(title, content)
    
    # Check if exact same content was sent
    if content_hash in sent_data.get("sent_hashes", []):
        logger.warning("Duplicate content detected (hash match): %s", title)
        return True
    
    # Check if same title was sent in last 10 posts
    if title in sent_data.get("sent_titles", [])[-10:]:
        logger.warning("Duplicate title detected: %s", title)
        return True
    
    # Check if same topic was used in last 3 posts (force rotation)
    if topic in sent_data.get("last_topics", [])[-3:]:
        logger.warning("Topic used too recently: %s", topic)
        return True
    
    return False


def _record_sent_post(title: str, content: str, topic: str, snippet: str | None = None) -> None:
    """Record a sent post with richer metadata for future analysis.

    - Keeps backward-compatible lists (`sent_titles`, `sent_hashes`, `last_topics`).
    - Appends a structured `sent_posts` entry used by the LLM to learn from our history.
    """
    sent_data = _load_sent_posts()
    content_hash = _get_content_hash(title, content)

    # Add/rotate compact tracking lists
    sent_data.setdefault("sent_titles", []).append(title)
    sent_data["sent_titles"] = sent_data["sent_titles"][-50:]

    sent_data.setdefault("sent_hashes", []).append(content_hash)
    sent_data["sent_hashes"] = sent_data["sent_hashes"][-50:]

    sent_data.setdefault("last_topics", []).append(topic)
    sent_data["last_topics"] = sent_data["last_topics"][-10:]

    # Add detailed post record for LLM training/prompting
    sent_posts = sent_data.setdefault("sent_posts", [])
    sent_posts.append({
        "title": title,
        "excerpt": content.strip()[:300],
        "snippet": (snippet or content).strip()[:1000],
        "topic": topic,
        "date": datetime.now().isoformat()
    })
    # Keep a reasonable history size
    sent_data["sent_posts"] = sent_posts[-100:]

    sent_data["last_sent"] = datetime.now().isoformat()

    _save_sent_posts(sent_data)

# Affiliate links
AFFILIATE_LINKS = {
    "affiliate_hostinger": "https://hostinger.com/horizons?REFERRALCODE=VMKMILDHI76M",
    "affiliate_lovable": "https://lovable.dev/?via=daniel-wray",
    "affiliate_openphone": "https://get.openphone.com/u8t88cu9allj",
    "affiliate_veed": "https://veed.cello.so/Y4hEgduDP5L",
    "affiliate_elevenlabs": "https://try.elevenlabs.io/2dh4kqbqw25i",
    "affiliate_manychat": "https://manychat.partnerlinks.io/gal0gascf0ml",
    "affiliate_n8n": "https://n8n.partnerlinks.io/pxw8nlb4iwfh",
    "affiliate_brightdata": "https://get.brightdata.com/xafa5cizt3zw",
    "affiliate_cointiply": "http://www.cointiply.com/r/agAkz",
    "affiliate_ava": "https://meetava.sjv.io/anDyvY",
    "affiliate_theleap": "https://join.theleap.co/FyY11sd1KY",
    "affiliate_amazon": "https://amzn.to/4lICjtS",
    "affiliate_bolt": "https://get.business.bolt.eu/lx55rhexokw9"
}


def _get_recent_posts_for_prompt(limit: int = 6) -> str:
    """Return a JSON array (string) of recent sent posts to include in the LLM prompt.

    Each item includes: title, excerpt (short), snippet (longer), topic, date.
    """
    sent = _load_sent_posts().get("sent_posts", [])
    recent = sent[-limit:]
    try:
        return json.dumps(recent, ensure_ascii=False)
    except Exception:
        return "[]"


# -------------------- Business profile support --------------------
def _load_business_profile() -> Dict[str, Any]:
    """Load local business_profile.json if present; return dict."""
    profile_path = Path(__file__).parent.parent.parent / "business_profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("Failed to load business_profile.json")
    # Fallback: minimal profile built from env
    return {
        "primary_site": os.getenv("PRIMARY_SITE", "https://fdwa.site"),
        "about": os.getenv("BUSINESS_ABOUT", "FDWA builds custom AI automation workflows for SMBs."),
        "products": []
    }


def _load_knowledge_base() -> str:
    """Load FDWA knowledge base for strategic content generation."""
    kb_path = Path(__file__).parent.parent.parent / "FDWA_KNOWLEDGE_BASE.md"
    if kb_path.exists():
        try:
            with open(kb_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not load knowledge base: {e}")
    return ""


def _load_products_catalog() -> str:
    """Load FDWA products catalog for intelligent product recommendations."""
    catalog_path = Path(__file__).parent.parent.parent / "FDWA_PRODUCTS_CATALOG.md"
    if catalog_path.exists():
        try:
            with open(catalog_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not load products catalog: {e}")
    return ""


def _save_business_profile(profile: Dict[str, Any]) -> None:
    """Persist business_profile.json to repo root."""
    profile_path = Path(__file__).parent.parent.parent / "business_profile.json"
    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
    except Exception:
        logger.exception("Failed to save business_profile.json")


def scrape_buymeacoffee_shop(url: str) -> list:
    """Attempt to scrape a BuyMeACoffee shop page for product titles/prices.

    This is a best-effort helper (wrapped in try/except). If BeautifulSoup/requests
    are unavailable or parsing fails, returns an empty list.
    """
    try:
        from bs4 import BeautifulSoup

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        products = []

        # Look for obvious shop item containers
        # Best-effort: find elements that contain a price or the word 'Free'
        candidates = soup.find_all(lambda tag: tag.name in ["div", "li", "article"] and tag.get_text())
        seen = set()
        for c in candidates:
            text = c.get_text(separator=" ", strip=True)
            if len(text) < 20:
                continue
            # Find price or 'Free'
            m = re.search(r"\$\s?\d{1,4}", text)
            is_free = "free" in text.lower()
            if m or is_free:
                # Extract a short title (first 60 chars without price)
                title = re.sub(r"\$\s?\d{1,4}", "", text).strip()
                title = title[:120]
                price = 0 if is_free else float(m.group(0).replace("$", ""))
                key = (title, price)
                if key in seen:
                    continue
                seen.add(key)
                products.append({
                    "title": title,
                    "price": price,
                    "currency": "USD",
                    "availability": "free" if is_free else "paid",
                    "source": url
                })
                if len(products) >= 200:
                    break
        return products
    except Exception:
        logger.exception("BuyMeACoffee scraper failed for %s", url)
        return []


def update_business_profile_from_shop(urls: list) -> Dict[str, Any]:
    """Scrape provided shop URLs and merge findings into business_profile.json.

    Returns the updated profile dict.
    """
    profile = _load_business_profile()
    aggregated = profile.get("products", [])[:]

    for u in urls:
        scraped = scrape_buymeacoffee_shop(u)
        for p in scraped:
            # basic dedupe by title
            if not any(p["title"].lower() in (q.get("title","").lower()) for q in aggregated):
                aggregated.append(p)

    profile["products"] = aggregated
    _save_business_profile(profile)
    return profile

# ------------------ end business profile support --------------------


def generate_blog_content(trend_data: str, image_path: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Generate blog content using LLM (preferred) or templates with duplicate prevention."""
    logger.info("---GENERATING BLOG CONTENT---")

    # Remove any error or search system text from trend_data
    for bad in ["SERPAPI_SEARCH:", "TAVILY_SEARCH:", "Account out of searches", "error", "limit"]:
        if bad.lower() in (trend_data or "").lower():
            trend_data = ""
            break

    # Determine topic from trend data
    topic = "general"
    if trend_data:
        topic_lower = trend_data.lower()
        if any(word in topic_lower for word in ['marketing', 'social', 'growth', 'digital', 'sales', 'product']):
            topic = "marketing"
        elif any(word in topic_lower for word in ['finance', 'crypto', 'money', 'wealth', 'investment', 'credit', 'repair']):
            topic = "finance"
        elif any(word in topic_lower for word in ['ai', 'automation', 'artificial', 'tech', 'productivity', 'dispute']):
            topic = "ai"
        else:
            topic = "general"


    try:
        # LLM-first generation using centralized LLM provider. Honor BLOG_REQUIRE_LLM to forbid template fallbacks.
        try:
            from src.agent.llm_provider import get_llm
            
            # Get LLM with BlogPost structured output support (for Mistral)
            llm = get_llm(purpose="blog generation", structured_output_schema=BlogPost)
            
            require_llm = os.getenv("BLOG_REQUIRE_LLM", "false").lower() in ("1", "true", "yes")
            if not llm:
                msg = "No LLM provider available - using template fallback"
                logger.warning(msg)
                if require_llm:
                    raise RuntimeError("No LLM provider available and BLOG_REQUIRE_LLM is set to true")
                # Trigger template fallback by raising
                raise RuntimeError(msg)

            # --- Pre-generation: propose 3 candidate titles and reject duplicates early ---
            title_candidates = []
            try:
                title_prompt = (
                    "Given the INPUT DATA JSON and FDWA style guide, propose 3 engaging, non-generic blog titles that contain data or a clear benefit. "
                    "Return ONLY valid JSON: {\"titles\": [title1, title2, title3]}."
                    f"\n\nINPUT: {json.dumps({'topic': topic,'trend_data': trend_data})}"
                )
                try:
                    t_resp = llm.invoke(title_prompt)
                    t_text = t_resp.content if hasattr(t_resp, 'content') else str(t_resp)
                    json_match = re.search(r"\{.*\}", t_text, re.DOTALL)
                    if json_match:
                        t_text = json_match.group(0)
                    parsed_titles = json.loads(t_text)
                    title_candidates = parsed_titles.get('titles', []) if isinstance(parsed_titles, dict) else []
                except Exception:
                    # best-effort title generation failed — continue to full generation
                    title_candidates = []

                # Filter out duplicates using sent posts
                filtered = []
                for t in title_candidates:
                    if not _is_duplicate_post(t, t, topic):
                        filtered.append(t)
                title_candidates = filtered
            except Exception:
                title_candidates = []

            past_posts_json = _get_recent_posts_for_prompt(limit=6)

            business_profile = _load_business_profile()
            knowledge_base = _load_knowledge_base()
            products_catalog = _load_products_catalog()
            
            # Load blog writing style guide
            style_guide = ""
            try:
                style_guide_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "BLOG_WRITING_STYLE_GUIDE.md")
                if os.path.exists(style_guide_path):
                    with open(style_guide_path, encoding='utf-8') as f:
                        style_guide = f.read()
                    logger.info("Loaded blog writing style guide (%d chars)", len(style_guide))
            except Exception as e:
                logger.warning("Could not load style guide: %s", e)

            # Include richer context (if provided by graph) and make affiliate + resources requirements explicit
            ctx_payload = {
                "topic": topic,
                "trend_data": (trend_data or ""),
                "affiliate_links": {k: v for k, v in AFFILIATE_LINKS.items()},
                "our_recent_posts": json.loads(past_posts_json),
                "business_profile": business_profile,
                "knowledge_base_summary": knowledge_base[:3000] if knowledge_base else "No knowledge base loaded",
                "products_catalog_summary": products_catalog[:2000] if products_catalog else "No products catalog loaded",
            }

            # If pre-generated non-duplicate title candidates exist, pass them to the LLM as preferred titles
            if title_candidates:
                ctx_payload["suggested_titles"] = title_candidates

            if context and isinstance(context, dict):
                # merge caller-provided context (tweet text, insight, platform drafts)
                ctx_payload["caller_context"] = context

            prompt = json.dumps(ctx_payload)

            # Get current year for blog content
            from datetime import datetime
            current_year = datetime.now().year
            current_month = datetime.now().strftime("%B")

            generation_prompt = f"""
You are an expert content strategist and educational copywriter for FDWA (Futurist Digital Wealth Agency).

CURRENT DATE CONTEXT: It is {current_month} {current_year}. Use {current_year} in all examples, not 2025 or older years.

Your mission: Create FULL, DETAILED, EDUCATIONAL blog articles that teach, not just list. Break down topics, explain WHY tools matter, show HOW to apply information, include real data and examples.

MANDATORY: Embed at least 3 affiliate links from `affiliate_links`, include a clear `Resources & Links` section, and mention 2–3 FDWA products. Return ONLY valid JSON matching the output schema.

=== INPUT DATA (JSON) ===
{prompt}

=== BLOG WRITING STYLE GUIDE ===
{style_guide[:8000] if style_guide else "Write detailed, educational content with real examples and data."}

=== YOUR TASK ===

Create a comprehensive blog post (1000-1500 words) following this structure:

1. **OPENING HOOK** (100-200 words):
   - Start with real data/statistics from trend_data
   - Include specific numbers, growth rates, or compelling facts
   - Example: "Weather trading bots are generating thousands in monthly profits" with proof links
   - Set clear expectations for what readers will learn

2. **CONTEXT & CURRENT EVENTS** (150-300 words):
   - Latest trends and industry data from trend_data
   - Market statistics: "84% of organizations already use [technology]"
   - Real examples: "One trader grew $1,000 to $24,000 since April {current_year}"
   - Reference current month/year: {current_month} {current_year}
   - Why this matters NOW

3. **MAIN EDUCATIONAL CONTENT** (800-1200 words):
   
   **For Tool Guides:**
   - Organize by category (AI Automation, Business Banking, Content Creation, etc.)
   - Each tool gets: What it does + WHY you need it + Benefit/discount + Link
   - Example format:
     ```
     **n8n** – Build advanced automations without paying Zapier prices:
     https://n8n.partnerlinks.io/pxw8nlb4iwfh
     
     **Emergent** – Transform ideas into fully functional websites and mobile apps:
     https://get.emergent.sh/y62pekmn0zfq
     ```
   
   **For How-To/Tutorial:**
   - Step-by-step breakdown with numbered steps
   - Explain WHY each step matters, not just WHAT to do
   - Include actual commands/code if applicable
   - Troubleshooting tips
   - Optimization advice
   
   **For Concept/Strategy:**
   - Break down the meaning and implications
   - Multiple perspectives or approaches
   - Real-world application to FDWA's niches (credit, automation, business, finance)
   - Actionable tips readers can implement immediately

4. **THE REALITY CHECK** (100-200 words):
   - Be honest: "I read the manuals — it's a maze of contracts and forms"
   - Address real pain points and challenges
   - Show how FDWA's approach cuts through complexity
   - Build trust through transparency

5. **RESOURCES & LINKS SECTION**:
   - Relevant FDWA products (2-3 matched to topic)
   - Community: https://whop.com/futuristicwealth/
   - Newsletter: https://futuristic-wealth.beehiiv.com/
   - BuyMeACoffee: https://buymeacoffee.com/coinvest
   - LinkTree: https://linktr.ee/omniai
   - Consultation booking (pick appropriate type based on topic)
   - Website: https://fdwa.site

6. **DISCLAIMER** (if applicable):
   - Trading/investing: "Involves risk of loss. Use funds you can afford to lose."
   - Credit/legal: "We provide guidance, not legal advice."
   - Results: "Results vary; past performance not indicative of future."

=== AFFILIATE LINK INTEGRATION RULES ===

❌ WRONG: "Check out ElevenLabs for AI voice"

✅ RIGHT: "**ElevenLabs** – AI voice, narration, and audio content (10% discount):
https://try.elevenlabs.io/2dh4kqbqw25i"

Integrate 3-5 affiliate links naturally:
- From affiliate_links provided
- Match to content topic
- Include benefit/discount
- Explain WHY reader needs it

=== FDWA PRODUCT RECOMMENDATIONS ===

Match to topic keywords from trend_data:
- **AI/automation** → AI Vibe Coding Bootcamp, Social Media Game Plan, n8n, Blackbox AI
- **Credit/finance** → 72 Hour Credit Hack, Ultimate Credit Vault, AVA Finance, NAV
- **Business/marketing** → 50 Business Ideas, Digital products, ManyChat, Beehiiv

=== CONSULTATION BOOKING LINKS ===

Pick ONE based on primary topic:
- **AI/automation focus** → https://cal.com/bookme-daniel/ai-consultation-smb
- **Credit/finance focus** → https://cal.com/bookme-daniel/credit-consultation
- **General business** → https://cal.com/bookme-daniel/30min

=== WRITING TONE ===

✅ DO:
- Conversational but authoritative: "We're back with more valuable information"
- Data-driven: Back every claim with numbers
- Honest: "Trust me — I run up a serious bill with AI tools"
- Educational: Teach, don't just pitch
- Action-oriented: Tell readers exactly what to do

❌ DON'T:
- Generic fluff: "In today's digital age..."
- Weak CTAs: "Click here to learn more"
- Just listing without explaining WHY/HOW
- Overly salesy without education first

=== OUTPUT FORMAT (VALID JSON ONLY) ===

{{
  "title": "engaging title with data or specific benefit (not generic)",
  "html": "1000-1500 word detailed HTML article with:
    - Opening hook with statistics (100-200 words)
    - Context & trends section (150-300 words)
    - Main educational content (800-1200 words) with <h2>/<h3> headers
    - Real examples with specific numbers
    - 3-5 affiliate links embedded naturally with benefits explained
    - 2-3 FDWA products mentioned contextually
    - Reality check section (honest about challenges)
    - Resources section with all FDWA links
    - Disclaimer if needed
    - Appropriate consultation CTA",
  "excerpt": "compelling 1-2 sentence hook mentioning data or specific outcome",
  "rationale": ["how this improves on past posts", "unique angle taken", "specific value provided"],
  "products_mentioned": ["FDWA product 1", "FDWA product 2"],
  "affiliate_tools_used": ["tool 1", "tool 2", "tool 3"],
  "consultation_type": "ai" or "credit" or "general",
  "word_count": 1200
}}

Return ONLY valid JSON. NO text before or after the JSON object.
"""

            # Retry LLM invocation (configurable via env)
            # Reduced default retries to prevent "stuck" behavior
            max_retries = int(os.getenv("BLOG_LLM_MAX_RETRIES", "1"))
            backoff = float(os.getenv("BLOG_LLM_RETRY_BACKOFF", "1.0"))
            
            # --- Content-quality validation function ---
            def _quality_check(html_text: str) -> tuple[bool, str]:
                plain = re.sub(r"<[^>]+>", "", html_text or "")
                wc = len(plain.split())
                if wc < 900:
                    return False, "too_short"

                found_aff = 0
                for link in AFFILIATE_LINKS.values():
                    if link in (html_text or ""):
                        found_aff += 1
                if found_aff < 3:
                    return False, "missing_affiliates"

                if not re.search(r"resources|resources and links|resources & links", html_text or "", re.I):
                    return False, "missing_resources_section"

                return True, "ok"

            # Global uniqueness loop
            max_unique_attempts = 2  # Reduced from 3 to 2
            unique_attempts_done = 0
            avoid_titles = []
            
            while unique_attempts_done < max_unique_attempts:
                unique_attempts_done += 1
                
                current_prompt = generation_prompt
                if avoid_titles:
                     current_prompt += f"\n\nIMPORTANT: Do NOT use the following titles as they are duplicates: {json.dumps(avoid_titles)}. Create a fresh, unique title."

                # Inner loop: API reliability retries
                response = None
                last_exc = None
                for attempt in range(1, max_retries + 1):
                    try:
                        response = llm.invoke(current_prompt)
                        break
                    except Exception as e:
                        last_exc = e
                        logger.warning("LLM attempt %d/%d failed: %s", attempt, max_retries, str(e)[:200])
                        if attempt == max_retries:
                            logger.error("LLM generation failed after %d attempts", max_retries)
                            raise
                        sleep_for = backoff * (2 ** (attempt - 1))
                        time.sleep(sleep_for)

                # Handle structured output (Pydantic BlogPost) or text response
                if isinstance(response, BlogPost):
                    # Structured output from Mistral with_structured_output()
                    logger.info("Received structured BlogPost from LLM")
                    title = response.title
                    html_output = response.html
                    excerpt = response.excerpt
                else:
                    # Text response from HuggingFace or fallback - parse JSON
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    response_text = response_text.strip()
                    
                    # Check if response is empty
                    if not response_text:
                        logger.warning("LLM returned empty response")
                        if unique_attempts_done == max_unique_attempts:
                             raise ValueError("Empty LLM response")
                        continue
                    
                    # Extract JSON from response (handle wrapped JSON)
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
                    
                    try:
                        parsed = json.loads(response_text)
                        title = parsed.get("title")
                        html_output = parsed.get("html")
                        excerpt = parsed.get("excerpt", "")
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse LLM JSON: %s", e)
                        if unique_attempts_done == max_unique_attempts:
                            raise ValueError(f"Invalid JSON from LLM: {e}")
                        continue

                # Content-quality validation + optional content-level retries
                content_retries = int(os.getenv("BLOG_LLM_CONTENT_RETRIES", "1"))
                content_attempt = 0
                quality_ok, quality_reason = _quality_check(html_output)
                while not quality_ok and content_attempt < content_retries:
                    content_attempt += 1
                    logger.warning("LLM content-quality check failed (%s). Content retry %d/%d", quality_reason, content_attempt, content_retries)
                    regen_note = (
                        "\n\nIMPORTANT: previous output missed: %s. Regenerate the blog and ensure it contains at least 1000 words, includes 3-5 affiliate links, a 'Resources' section, and mentions FDWA products. Return ONLY valid JSON." % quality_reason
                    )
                    try:
                        response = llm.invoke(current_prompt + regen_note)
                    except Exception as e:
                        logger.warning("Content retry invoke failed: %s", e)
                        break

                    # parse regenerated response
                    if isinstance(response, BlogPost):
                        title = response.title
                        html_output = response.html
                        excerpt = response.excerpt
                    else:
                        response_text = response.content if hasattr(response, 'content') else str(response)
                        response_text = response_text.strip()
                        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                        if json_match:
                            response_text = json_match.group(0)
                        parsed = json.loads(response_text)
                        title = parsed.get("title")
                        html_output = parsed.get("html")
                        excerpt = parsed.get("excerpt", "")

                    quality_ok, quality_reason = _quality_check(html_output)
                    if quality_ok:
                        logger.info("Content retry succeeded on attempt %d", content_attempt)
                        break
                    time.sleep(0.5 * content_attempt)

                
                # Validate required fields
                if not title or not html_output:
                    logger.warning("LLM response missing title or html")
                    if unique_attempts_done == max_unique_attempts:
                        raise ValueError("Missing required fields in LLM response")
                    continue
                
                # Check for duplicates
                if _is_duplicate_post(title, excerpt or html_output[:200], topic):
                    logger.warning("LLM generated duplicate content: %s. Retrying...", title)
                    avoid_titles.append(title)
                    if unique_attempts_done == max_unique_attempts:
                        raise ValueError("Duplicate content detected after multiple attempts")
                    continue
                
                # If unique and valid, break the loop
                break
            
            # Add image to blog HTML
            image_html = ""
            image_url = image_path or os.environ.get("BLOG_IMAGE_URL")
            if image_url and image_url.startswith(('http://', 'https://')):
                image_html = f'<img src="{image_url}" alt="Blog Image" style="max-width:100%;border-radius:12px;margin-bottom:20px;display:block;" />\n'
            
            blog_html = image_html + html_output

            # Ensure primary site CTA/link is present in the blog HTML. If the LLM omitted
            # our CTA, append a short call-to-action paragraph so every blog includes the link.
            primary_site = os.getenv("PRIMARY_SITE", "https://fdwa.site")
            try:
                if primary_site and "fdwa.site" not in (blog_html or "").lower():
                    cta_html = (
                        f"<p style=\"margin-top:18px;font-weight:600;\">Learn more about AI automation and FDWA services: "
                        f"<a href=\"{primary_site}\" target=\"_blank\">{primary_site}</a></p>"
                    )
                    blog_html = blog_html + "\n" + cta_html
            except Exception:
                # non-critical if CTA append fails
                pass
            logger.info("✅ LLM-generated blog created: %s", title)
            return {
                "blog_html": blog_html,
                "title": title,
                "topic": topic,
                "intro_paragraph": excerpt,
                "image_url": image_url
            }
                
        except Exception as llm_exc:
            logger.warning("LLM blog generation failed: %s", str(llm_exc)[:200])
            raise llm_exc

    except Exception as e:
        logger.exception("Error generating blog content: %s", e)
        return {"error": str(e)}

def send_blog_email(blog_html: str, title: str, image_url: str | None = None) -> Dict[str, Any]:
    """Send blog content via Gmail with image URL in HTML body.
    
    Args:
        blog_html: HTML content of the blog post (image URL already embedded).
        title: Subject/title of the email.
        image_url: Optional image URL (for logging/reference only, already in HTML).
        
    Returns:
        Dictionary with email status.
    """
    logger.info("---SENDING BLOG EMAIL---")
    
    try:
        blogger_email = os.getenv("BLOGGER_EMAIL", "mildhighent.moneyovereverything@blogger.com")
        
        # Check if image URL is in the HTML
        has_image = image_url and image_url in blog_html
        if has_image:
            logger.info("Email HTML contains image URL: %s", image_url[:60] if image_url else "None")
        else:
            logger.info("Email HTML does not contain an image")
        
        # Send email using Composio Gmail - image URL is already in the HTML body
        email_params = {
            "recipient_email": blogger_email,
            "subject": title,
            "body": blog_html,
            "is_html": True,
            "user_id": "me"
        }
        
        email_response = composio_client.tools.execute(
            "GMAIL_SEND_EMAIL",
            email_params,
            connected_account_id=os.getenv("GMAIL_CONNECTED_ACCOUNT_ID")
        )
        
        logger.info("Gmail response: %s", email_response)
        
        if email_response.get("successful", False):
            logger.info("Blog email sent successfully!")
            return {
                "email_status": "Sent successfully", 
                "recipient": blogger_email,
                "has_image": has_image
            }
        else:
            error_msg = email_response.get("error", "Unknown error")
            logger.error("Gmail send failed: %s", error_msg)
            return {"email_status": f"Failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Email sending failed: %s", e)
        return {"email_status": f"Failed: {str(e)}"}


def generate_and_send_blog(trend_data: str = None, image_url: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Generate blog content and send via email.
    
    Args:
        trend_data: Trend data to use for content generation.
        image_url: Optional URL of image to include in the blog.
        
    Returns:
        Dictionary with blog and email status.
    """
    logger.info("Starting blog generation and email process...")
    
    # Get image URL from various sources (must be a URL, not local path)
    image_source = image_url or os.environ.get("BLOG_IMAGE_URL")
    
    if image_source:
        logger.info("Image URL for blog: %s", image_source[:60] if image_source else "None")
    
    # Always require trend_data for unique blog content
    if not trend_data or not trend_data.strip():
        # Get current year for fallback trends
        from datetime import datetime
        current_year = datetime.now().year
        
        fallback_trends = [
            "AI automation trends show 300% increase in small business adoption. Workflow automation saves 15+ hours per week.",
            f"Digital product sales are booming in {current_year}, with entrepreneurs earning passive income from ebooks and guides.",
            "Credit repair with AI is helping thousands improve their scores faster than ever before.",
            "Business automation tools are saving SMBs 20+ hours per week and increasing revenue.",
            "Financial empowerment through tech: more people are using AI to manage money and build wealth.",
            "Social media marketing strategies are evolving with AI-powered content creation tools.",
            "Entrepreneurs are building multiple income streams through digital products and automation.",
            "The gig economy is transforming with AI tools that help freelancers scale their businesses."
        ]
        trend_data = random.choice(fallback_trends)

    # Generate blog content with image URL embedded in HTML
    blog_result = generate_blog_content(trend_data, image_path=image_source, context=context)

    if "error" in blog_result:
        return blog_result

    # Send email - image URL is already in the HTML body
    email_result = send_blog_email(
        blog_result["blog_html"], 
        blog_result["title"],
        image_url=blog_result.get("image_url")  # Pass for logging
    )

    # Record the sent post to prevent future duplicates (include snippet for analysis)
    if email_result.get("email_status", "").startswith("Sent"):
        _record_sent_post(
            blog_result["title"],
            blog_result.get("intro_paragraph", ""),
            blog_result["topic"],
            snippet=blog_result.get("blog_html", "")[:1000]
        )
        logger.info("Recorded sent post to prevent duplicates and for learning: %s", blog_result["title"])

    # Combine results
    return {
        "blog_title": blog_result["title"],
        "blog_topic": blog_result["topic"],
        "email_status": email_result["email_status"],
        "recipient": email_result.get("recipient", ""),
        "has_image": email_result.get("has_image", False),
        "image_url": blog_result.get("image_url", ""),
        "blog_html_preview": blog_result["blog_html"][:200] + "..."
    }