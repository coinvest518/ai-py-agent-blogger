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

import requests
from composio import Composio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Composio client
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    toolkit_versions={
        "gmail": os.getenv("COMPOSIO_TOOLKIT_VERSION_GMAIL")
    }
)

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


def _is_duplicate_post(title: str, content: str, topic: str, check_topic: bool = True) -> bool:
    """Check if this post has already been sent recently.
    
    Args:
        title: Post title to check
        content: Post content to check
        topic: Post topic to check
        check_topic: If False, skip topic recency check (used on final retry)
    """
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
    
    # Check if same topic was used in last 3 posts (force rotation) - can be disabled on final retry
    if check_topic and topic in sent_data.get("last_topics", [])[-3:]:
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
        # LLM-first generation using centralized LLM provider
        try:
            from src.agent.llm_provider import get_llm
            
            # Do NOT use structured_output_schema — it forces function-calling which
            # fails when the HTML content is large.  Plain text + delimiter parsing is
            # far more reliable for long-form HTML.
            llm = get_llm(purpose="blog generation")
            
            require_llm = os.getenv("BLOG_REQUIRE_LLM", "false").lower() in ("1", "true", "yes")
            if not llm:
                msg = "No LLM provider available - using template fallback"
                logger.warning(msg)
                if require_llm:
                    raise RuntimeError("No LLM provider available and BLOG_REQUIRE_LLM is set to true")
                raise RuntimeError(msg)

            # Skip separate title pre-generation — saves 1 LLM call.
            # The main generation prompt handles title creation.

            past_posts_json = _get_recent_posts_for_prompt(limit=6)

            business_profile = _load_business_profile()
            knowledge_base = _load_knowledge_base()
            products_catalog = _load_products_catalog()
            
            # Load recent topics to force rotation and avoid duplicates
            sent_data = _load_sent_posts()
            recent_topics = sent_data.get("last_topics", [])[-3:]  # Last 3 topics used
            logger.info("Recent topics to avoid: %s", recent_topics)
            
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

            # Build context payload
            ctx_payload = {
                "topic": topic,
                "trend_data": (trend_data or ""),
                "affiliate_links": {k: v for k, v in AFFILIATE_LINKS.items()},
                "our_recent_posts": json.loads(past_posts_json),
                "recent_topics_to_avoid": recent_topics,
                "business_profile": business_profile,
                "knowledge_base_summary": knowledge_base[:3000] if knowledge_base else "",
                "products_catalog_summary": products_catalog[:2000] if products_catalog else "",
            }

            if context and isinstance(context, dict):
                ctx_payload["caller_context"] = context

            prompt = json.dumps(ctx_payload)

            # Get current year for blog content
            from datetime import datetime
            current_year = datetime.now().year
            current_month = datetime.now().strftime("%B")
            
            # Add note about recent topics if we have them
            avoid_topics_note = ""
            if recent_topics:
                avoid_topics_note = f"\n\nIMPORTANT: We recently posted about these topics: {', '.join(recent_topics)}. Choose a DIFFERENT topic category (marketing, AI/tech, crypto, automation, etc.) to ensure content variety."

            generation_prompt = f"""You are an expert content strategist for FDWA (Futurist Digital Wealth Agency).
It is {current_month} {current_year}.{avoid_topics_note}

Create a 1000-1500 word educational blog post. Embed at least 3 affiliate links, include a Resources section, and mention 2-3 FDWA products.

=== INPUT DATA ===
{prompt}

=== STYLE ===
{style_guide[:4000] if style_guide else "Write detailed, educational content."}

=== STRUCTURE ===
1. Opening hook with data/stats (100-200 words)
2. Context & trends (150-300 words)
3. Main educational content with <h2>/<h3> headers (800-1200 words)
4. Reality check — be honest about challenges
5. Resources section (FDWA products, community links, consultation booking)
6. Disclaimer if applicable

=== AFFILIATE LINKS (use 3-5) ===
- n8n: https://n8n.partnerlinks.io/pxw8nlb4iwfh
- Hostinger: https://hostinger.com/horizons?REFERRALCODE=VMKMILDHI76M
- ElevenLabs: https://try.elevenlabs.io/2dh4kqbqw25i
- ManyChat: https://manychat.partnerlinks.io/gal0gascf0ml
- Lovable: https://lovable.dev/?via=daniel-wray
- VEED: https://veed.cello.so/Y4hEgduDP5L
- BrightData: https://get.brightdata.com/xafa5cizt3zw

=== FDWA LINKS ===
- Community: https://whop.com/futuristicwealth/
- Newsletter: https://futuristic-wealth.beehiiv.com/
- Website: https://fdwa.site
- AI consultation: https://cal.com/bookme-daniel/ai-consultation-smb
- Credit consultation: https://cal.com/bookme-daniel/credit-consultation

=== OUTPUT FORMAT ===
Use these EXACT delimiters (not JSON). Do NOT wrap in code blocks or quotes.

===TITLE===
Your engaging blog title here
===EXCERPT===
A compelling 1-2 sentence hook
===HTML===
<h1>Your title</h1>
<p>Full HTML article here...</p>
"""

            # Single LLM call — no retries for content quality, just reliability retry
            max_retries = int(os.getenv("BLOG_LLM_MAX_RETRIES", "2"))
            backoff = float(os.getenv("BLOG_LLM_RETRY_BACKOFF", "2.0"))

            response = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = llm.invoke(generation_prompt)
                    break
                except Exception as e:
                    logger.warning("LLM attempt %d/%d failed: %s", attempt, max_retries, str(e)[:200])
                    if attempt == max_retries:
                        raise
                    time.sleep(backoff * attempt)

            # Parse the delimiter-based response
            response_text = response.content if hasattr(response, 'content') else str(response)
            response_text = response_text.strip()

            if not response_text:
                raise ValueError("Empty LLM response")

            # Extract using delimiters
            title = ""
            excerpt = ""
            html_output = ""

            if "===TITLE===" in response_text:
                # Delimiter format (preferred)
                parts = response_text.split("===TITLE===")
                after_title = parts[-1] if len(parts) > 1 else response_text

                if "===EXCERPT===" in after_title:
                    title_part, rest = after_title.split("===EXCERPT===", 1)
                    title = title_part.strip()
                    if "===HTML===" in rest:
                        excerpt_part, html_part = rest.split("===HTML===", 1)
                        excerpt = excerpt_part.strip()
                        html_output = html_part.strip()
                    else:
                        excerpt = rest.strip()
                elif "===HTML===" in after_title:
                    title_part, html_part = after_title.split("===HTML===", 1)
                    title = title_part.strip()
                    html_output = html_part.strip()
                else:
                    title = after_title[:200].strip()
                    html_output = after_title.strip()
            else:
                # Fallback: try JSON parsing with fixing
                logger.info("Delimiter format not found, trying JSON fallback")
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                    # Fix common LLM JSON escape issues
                    json_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', json_text)
                    try:
                        parsed = json.loads(json_text)
                        title = parsed.get("title", "")
                        html_output = parsed.get("html", "")
                        excerpt = parsed.get("excerpt", "")
                    except json.JSONDecodeError:
                        # Last resort: treat entire response as HTML
                        logger.warning("JSON parse failed, using response as raw HTML")
                        html_output = response_text
                        # Try to extract title from HTML
                        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', response_text, re.I | re.DOTALL)
                        title = h1_match.group(1).strip() if h1_match else f"FDWA Blog: {topic.title()} Insights"
                        excerpt = ""
                else:
                    # Treat as raw HTML
                    html_output = response_text
                    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', response_text, re.I | re.DOTALL)
                    title = h1_match.group(1).strip() if h1_match else f"FDWA Blog: {topic.title()} Insights"

            # Validate we got something
            if not title:
                title = f"FDWA: {topic.title()} in {current_month} {current_year}"
            if not html_output:
                raise ValueError("LLM produced no HTML content")

            # Strip any markdown code fences the LLM may have wrapped around HTML
            html_output = re.sub(r'^```html?\s*\n?', '', html_output)
            html_output = re.sub(r'\n?```\s*$', '', html_output)

            logger.info("Blog parsed: title=%s, html=%d chars", title[:60], len(html_output))

            # Check for duplicates
            if _is_duplicate_post(title, excerpt or html_output[:200], topic, check_topic=False):
                logger.warning("Blog title is duplicate, appending timestamp")
                title = f"{title} ({current_month} {current_year})"
            
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