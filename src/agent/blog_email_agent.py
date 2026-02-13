"""Blog Email Agent for FDWA AI Automation Agency.

This agent generates blog content using predefined templates and sends it via Gmail.
Image URLs are embedded directly in the HTML body for display.
"""

import hashlib
import json
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from composio import Composio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Composio client
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id="default"
)

# Configure logging
logger = logging.getLogger(__name__)

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
            with open(SENT_POSTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Ensure new keys exist for backward compatibility
                data.setdefault("sent_posts", [])
                data.setdefault("sent_titles", [p.get("title") for p in data.get("sent_posts", []) if p.get("title")])
                data.setdefault("sent_hashes", data.get("sent_hashes", []))
                data.setdefault("last_topics", data.get("last_topics", []))
                return data
        except (json.JSONDecodeError, IOError):
            pass

    return {"sent_posts": [], "sent_titles": [], "sent_hashes": [], "last_topics": []}


def _save_sent_posts(data: Dict[str, Any]) -> None:
    """Save the record of sent blog posts."""
    try:
        with open(SENT_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
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


def _record_sent_post(title: str, content: str, topic: str, snippet: Optional[str] = None) -> None:
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

# Blog HTML Templates
TEMPLATE_AI_BUSINESS = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>Why Strategic Consulting Transforms Business Operations</h2>
<p>Smart entrepreneurs are leveraging expert consulting to:</p>
<ul>
  <li>Eliminate inefficient processes</li>
  <li>Scale operations without unnecessary costs</li>
  <li>Improve customer experience through better strategies</li>
  <li>Generate more revenue with optimized approaches</li>
</ul>

<h2>Essential Tools for Business Growth</h2>
<p>Here are the game-changing tools successful businesses are using:</p>
<ul>
  <li><strong>Website & Hosting:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Professional hosting that scales with your business</li>
  <li><strong>Business Development:</strong> <a href="{affiliate_lovable}" target="_blank">Lovable</a> - Build solutions without coding</li>
  <li><strong>Business Communication:</strong> <a href="{affiliate_openphone}" target="_blank">OpenPhone</a> - Professional phone system</li>
  <li><strong>Content Creation:</strong> <a href="{affiliate_veed}" target="_blank">Veed</a> - AI video editing made simple</li>
  <li><strong>Voice Solutions:</strong> <a href="{affiliate_elevenlabs}" target="_blank">ElevenLabs</a> - Professional AI voice generation</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Start Your Business Transformation Today</h2>
<p>The businesses that adopt strategic consulting now will dominate their markets tomorrow. Don't wait - your competitors are already getting ahead.</p>

<p><strong>Ready to scale your business?</strong> Visit <a href="https://fdwa.site" target="_blank">FDWA</a> for expert AI consulting and implementation.</p>

<p><em>Transform your business operations, increase efficiency, and unlock new revenue streams with proven strategies.</em></p>

Labels: business, consulting, growth, entrepreneurship, scaling"""

TEMPLATE_MARKETING = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>The Strategic Marketing Revolution</h2>
<p>Modern businesses are winning with smart strategic approaches:</p>
<ul>
  <li>Automated customer acquisition systems</li>
  <li>Data-driven content creation workflows</li>
  <li>Analytics-based decision making</li>
  <li>Scalable marketing automation</li>
</ul>

<h2>Must-Have Tools for Business Growth</h2>
<p>Build your business stack with these proven tools:</p>
<ul>
  <li><strong>Chatbot Automation:</strong> <a href="{affiliate_manychat}" target="_blank">ManyChat</a> - Engage customers 24/7</li>
  <li><strong>Workflow Automation:</strong> <a href="{affiliate_n8n}" target="_blank">n8n</a> - Connect all your business tools</li>
  <li><strong>Web Hosting:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Fast, reliable hosting</li>
  <li><strong>Video Marketing:</strong> <a href="{affiliate_veed}" target="_blank">Veed</a> - Create engaging video content</li>
  <li><strong>Data Collection:</strong> <a href="{affiliate_brightdata}" target="_blank">BrightData</a> - Market research and insights</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Scale Your Business Impact</h2>
<p>Stop competing on price and start competing on value. Smart strategies let you deliver personalized experiences at scale.</p>

<p>Get professional business strategy and implementation at <a href="https://fdwa.site" target="_blank">FDWA</a>.</p>

Labels: marketing, strategy, growth, business, consulting"""

TEMPLATE_FINANCIAL = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>Building Financial Success in Business</h2>
<p>Smart entrepreneurs are diversifying with:</p>
<ul>
  <li>Strategic financial planning</li>
  <li>Automated investment strategies</li>
  <li>Revenue stream optimization</li>
  <li>Technology-driven business models</li>
</ul>

<h2>Financial Tools for Modern Entrepreneurs</h2>
<p>Maximize your earning potential with these platforms:</p>
<ul>
  <li><strong>Financial Management:</strong> <a href="{affiliate_ava}" target="_blank">Ava</a> - Smart money management</li>
  <li><strong>Digital Products:</strong> <a href="{affiliate_theleap}" target="_blank">The Leap</a> - Create and sell digital products</li>
  <li><strong>E-commerce:</strong> <a href="{affiliate_amazon}" target="_blank">Amazon</a> - Everything for your business</li>
  <li><strong>Business Infrastructure:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Professional web presence</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Your Financial Future Starts Now</h2>
<p>The wealth gap is widening between those who embrace strategy and those who don't. Which side will you be on?</p>

<p>Learn advanced financial strategies at <a href="https://fdwa.site" target="_blank">FDWA</a>.</p>

Labels: finance, strategy, wealth, business, consulting"""

TEMPLATE_GENERAL = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>The Productivity Revolution</h2>
<p>High-performing entrepreneurs focus on:</p>
<ul>
  <li>Automating routine business tasks</li>
  <li>Building scalable systems and processes</li>
  <li>Leveraging technology for competitive advantage</li>
  <li>Creating multiple revenue streams</li>
</ul>

<h2>Essential Business Tools</h2>
<p>Build your business infrastructure with these tools:</p>
<ul>
  <li><strong>Web Presence:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Professional hosting and domains</li>
  <li><strong>App Development:</strong> <a href="{affiliate_lovable}" target="_blank">Lovable</a> - No-code app creation</li>
  <li><strong>Communication:</strong> <a href="{affiliate_openphone}" target="_blank">OpenPhone</a> - Business phone system</li>
  <li><strong>Content Creation:</strong> <a href="{affiliate_veed}" target="_blank">Veed</a> - Professional video editing</li>
  <li><strong>Business Supplies:</strong> <a href="{affiliate_amazon}" target="_blank">Amazon</a> - Everything you need</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Take Action Today</h2>
<p>Success in business comes from taking consistent action with the right tools and strategies. Start building your empire today.</p>

<p>Get expert business consulting and strategy at <a href="https://fdwa.site" target="_blank">FDWA</a>.</p>

Labels: business, productivity, entrepreneurship, tools, fdwa, success"""

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


def get_template_by_topic(topic: str) -> str:
    """Select appropriate template based on topic keywords."""
    topic_lower = topic.lower()
    
    if any(word in topic_lower for word in ['ai', 'automation', 'artificial', 'machine learning', 'tech', 'productivity']):
        return TEMPLATE_AI_BUSINESS
    elif any(word in topic_lower for word in ['marketing', 'social', 'growth', 'digital', 'sales', 'advertising']):
        return TEMPLATE_MARKETING
    elif any(word in topic_lower for word in ['finance', 'crypto', 'money', 'wealth', 'investment', 'financial']):
        return TEMPLATE_FINANCIAL
    else:
        return TEMPLATE_GENERAL


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
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("Failed to load business_profile.json")
    # Fallback: minimal profile built from env
    return {
        "primary_site": os.getenv("PRIMARY_SITE", "https://fwda.site"),
        "about": os.getenv("BUSINESS_ABOUT", "FWDA builds custom AI automation workflows for SMBs."),
        "products": []
    }


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
        import re
        import requests
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


def generate_blog_content(trend_data: str, image_path: Optional[str] = None) -> Dict[str, Any]:
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

    # EXPANDED content variations per topic - multiple options to prevent repetition
    content_variations = {
        "ai": [
            {
                "title": "AI Automation for Credit Repair and Business Success",
                "intro_paragraph": "Smart entrepreneurs are using AI to fix credit issues and automate their businesses. From dispute letter generators to report analyzers, AI tools are revolutionizing how people build wealth and streamline operations.",
                "main_content_header": "Why AI Beats Traditional Methods",
                "main_content": "People using AI for credit repair see results in weeks, not months. Automated dispute systems work 24/7, generating letters that get denials overturned. Business automation saves 20+ hours per week while increasing revenue through passive income streams."
            },
            {
                "title": "How AI is Transforming Small Business Operations in 2025",
                "intro_paragraph": "The AI revolution isn't just for big tech - small businesses are now leveraging powerful automation tools to compete with industry giants. From customer service chatbots to automated marketing, AI is leveling the playing field.",
                "main_content_header": "Real Results from AI Implementation",
                "main_content": "Small businesses using AI report 40% reduction in operational costs and 60% faster customer response times. Automated workflows handle repetitive tasks while entrepreneurs focus on growth and strategy."
            },
            {
                "title": "Building Your AI-Powered Business Empire",
                "intro_paragraph": "The entrepreneurs who embrace AI today will dominate their markets tomorrow. From content creation to customer analytics, AI tools are creating new opportunities for wealth building at unprecedented speed.",
                "main_content_header": "The AI Advantage for Modern Entrepreneurs",
                "main_content": "AI-powered businesses scale faster and operate more efficiently. Automated systems handle lead generation, content creation, and customer follow-ups while you focus on high-value activities."
            },
            {
                "title": "Automate Your Way to Financial Freedom with AI",
                "intro_paragraph": "Passive income streams powered by AI are helping ordinary people build extraordinary wealth. From automated affiliate marketing to AI-driven content businesses, the opportunities are endless.",
                "main_content_header": "Creating Automated Income Streams",
                "main_content": "AI enables you to create systems that work 24/7 generating revenue. Whether it's automated email sequences, AI-powered chatbots, or content creation workflows, technology multiplies your earning potential."
            }
        ],
        "marketing": [
            {
                "title": "Digital Product Marketing: Sell Ebooks and Guides Online",
                "intro_paragraph": "Modern entrepreneurs are building passive income by creating and selling digital products. From credit repair guides to business automation templates, digital products provide freedom and financial security.",
                "main_content_header": "Digital Product Success Stories",
                "main_content": "Creators selling digital products report 300% ROI within the first year. From step-by-step guides to automation templates, these products sell themselves once set up. AI helps create content faster and market it effectively."
            },
            {
                "title": "Social Media Marketing Secrets for Business Growth",
                "intro_paragraph": "Successful brands are using strategic social media marketing to reach millions without spending millions. Learn the tactics that turn followers into customers and likes into revenue.",
                "main_content_header": "Maximizing Your Social Media ROI",
                "main_content": "Businesses that master social media marketing see 5x higher engagement rates. Consistent posting, authentic storytelling, and strategic use of AI tools create sustainable growth without burning out."
            },
            {
                "title": "Content Marketing Strategies That Drive Real Results",
                "intro_paragraph": "Content is still king in 2025, but the rules have changed. Learn how successful businesses are using content marketing to attract, engage, and convert their ideal customers.",
                "main_content_header": "Building a Content Engine for Your Business",
                "main_content": "Strategic content marketing generates 3x more leads than traditional advertising at 62% lower cost. The key is creating valuable content that solves real problems and positions you as an authority."
            },
            {
                "title": "Email Marketing Automation for Consistent Sales",
                "intro_paragraph": "Email remains the highest ROI marketing channel, and automation makes it even more powerful. Build sequences that nurture leads and close sales while you sleep.",
                "main_content_header": "Automated Email Sequences That Convert",
                "main_content": "Well-designed email automation generates an average of $42 for every $1 spent. Set up once, and watch your automated sequences turn subscribers into loyal customers day after day."
            }
        ],
        "finance": [
            {
                "title": "Credit Repair Hacks and Financial Empowerment",
                "intro_paragraph": "Financial freedom starts with fixing your credit and building wealth strategically. From dispute letters to investment automation, smart people are using proven methods to improve their financial future.",
                "main_content_header": "Credit Repair That Works",
                "main_content": "Successful credit repair involves knowing the laws and using the right tools. AI dispute writers create perfect letters that get results. Combined with passive income strategies, this creates true financial empowerment."
            },
            {
                "title": "Building Multiple Income Streams for Financial Security",
                "intro_paragraph": "The wealthy don't rely on a single income source - they build multiple streams of revenue. Learn how to diversify your income and create lasting financial security.",
                "main_content_header": "Diversification Strategies That Work",
                "main_content": "Successful entrepreneurs typically have 5-7 income streams. From digital products to affiliate marketing to service businesses, diversification protects you from economic uncertainty while maximizing earning potential."
            },
            {
                "title": "Mastering Your Finances: A Guide to Wealth Building",
                "intro_paragraph": "Wealth building isn't about getting rich quick - it's about making smart decisions consistently. Learn the proven strategies that turn modest incomes into substantial wealth over time.",
                "main_content_header": "The Fundamentals of Wealth Creation",
                "main_content": "Wealth builders focus on increasing income, reducing expenses, and investing the difference wisely. Combined with strategic credit management, these principles create a solid foundation for financial freedom."
            },
            {
                "title": "From Debt to Prosperity: Your Financial Transformation",
                "intro_paragraph": "No matter where you're starting, financial transformation is possible. Thousands have gone from crushing debt to comfortable prosperity using proven methods and the right tools.",
                "main_content_header": "Steps to Financial Transformation",
                "main_content": "Start by understanding your credit, creating a budget, and identifying opportunities to increase income. With strategic planning and consistent action, you can completely transform your financial situation."
            }
        ],
        "general": [
            {
                "title": "Building Wealth with AI and Digital Products",
                "intro_paragraph": "The future belongs to those who embrace technology for financial success. From credit repair automation to passive income creation, AI tools are democratizing wealth building for everyone.",
                "main_content_header": "Your Path to Financial Freedom",
                "main_content": "High-performing individuals use integrated tech stacks for credit repair, business automation, and wealth building. These systems deliver results through time savings, increased efficiency, and passive income generation."
            },
            {
                "title": "Entrepreneurship in the Digital Age: Your Success Blueprint",
                "intro_paragraph": "The barriers to starting a successful business have never been lower. With the right tools and strategies, anyone can build a thriving digital business from anywhere in the world.",
                "main_content_header": "Keys to Digital Business Success",
                "main_content": "Successful digital entrepreneurs focus on solving real problems, building systems, and leveraging automation. Start small, iterate based on feedback, and scale what works."
            },
            {
                "title": "Scaling Your Business with Strategic Systems",
                "intro_paragraph": "Growth without systems leads to chaos. Learn how successful entrepreneurs build scalable systems that allow their businesses to grow without burning out.",
                "main_content_header": "Building Systems for Scale",
                "main_content": "Scalable businesses run on documented processes and automated workflows. Create systems for every repeatable task, and you'll free yourself to focus on strategy and growth."
            },
            {
                "title": "The Modern Entrepreneur's Toolkit for Success",
                "intro_paragraph": "Success in today's business world requires the right tools and strategies. Discover the essential toolkit that successful entrepreneurs are using to build and scale their businesses.",
                "main_content_header": "Essential Tools for Modern Business",
                "main_content": "From hosting to communication to automation, the right tools can 10x your productivity. Invest in quality tools that save time and enable growth, and watch your business transform."
            }
        ]
    }

    try:
        variations = content_variations.get(topic, content_variations["general"])

        # LLM-first generation (Google -> Mistral). Honor BLOG_REQUIRE_LLM to forbid template fallbacks.
        try:
            def _get_preferred_llm():
                # Preferred order: Mistral -> Hugging Face Inference -> Google (last)

                # 1) Mistral (preferred when key present)
                try:
                    from langchain_mistralai import ChatMistralAI
                    mistral_key = os.getenv("MISTRAL_API_KEY")
                    if mistral_key:
                        mistral_model = os.getenv("BLOG_LLM_MODEL_MISTRAL", "mistral-large-2512")
                        mistral_temp = float(os.getenv("BLOG_LLM_TEMPERATURE", "0.25"))
                        logger.info("Initializing ChatMistralAI for blog generation")
                        return ChatMistralAI(model=mistral_model, temperature=mistral_temp, mistral_api_key=mistral_key)
                except Exception as e:
                    logger.debug("Mistral initialization failed: %s", e)

                # 2) Hugging Face Inference API via HTTP (matches HF router docs)
                try:
                    import requests
                    hf_token = os.getenv("HF_TOKEN")
                    if hf_token:
                        hf_model = os.getenv("BLOG_LLM_MODEL_HF", "HuggingFaceTB/SmolLM3-3B:hf-inference")
                        hf_temp = float(os.getenv("BLOG_LLM_TEMPERATURE", "0.25"))

                        class HFChatWrapper:
                            def __init__(self, model, token, temperature=0.25):
                                self.model = model
                                self.token = token
                                self.temperature = temperature

                            def invoke(self, prompt_text: str):
                                url = "https://router.huggingface.co/v1/chat/completions"
                                headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
                                payload = {
                                    "model": self.model,
                                    "messages": [{"role": "user", "content": prompt_text}],
                                    "temperature": float(self.temperature)
                                }
                                try:
                                    resp = requests.post(url, headers=headers, json=payload, timeout=60)
                                    resp.raise_for_status()
                                    data = resp.json()
                                    content = data["choices"][0]["message"]["content"]
                                except requests.HTTPError as http_err:
                                    status = getattr(http_err.response, 'status_code', None)
                                    if status == 401:
                                        raise RuntimeError("Hugging Face Inference API: Unauthorized (HTTP 401). Check HF_TOKEN and grant 'Inference' permission or regenerate token.") from http_err
                                    if status == 429:
                                        raise RuntimeError("Hugging Face Inference API: Rate limited (HTTP 429). Check quota or retry later.") from http_err
                                    raise RuntimeError(f"Hugging Face Inference API HTTP error: {http_err}") from http_err
                                except Exception as e:
                                    raise RuntimeError(f"Hugging Face Inference API request failed: {e}") from e

                                # mimic LangChain ChatModel response object with `content` attr
                                class _R:
                                    def __init__(self, c):
                                        self.content = c

                                return _R(content)

                        logger.info("Initializing Hugging Face Inference wrapper for blog generation")
                        return HFChatWrapper(hf_model, hf_token, hf_temp)
                except Exception as e:
                    logger.debug("Hugging Face LLM unavailable: %s", e)

                # 3) Google as last resort (kept for compatibility)
                try:
                    from langchain_google_genai import GoogleGenerativeAI
                    ga_key = os.getenv("GOOGLE_AI_API_KEY")
                    if ga_key:
                        llm_model = os.getenv("BLOG_LLM_MODEL", "gemini-2.0-flash")
                        llm_temp = float(os.getenv("BLOG_LLM_TEMPERATURE", "0.25"))
                        logger.info("Initializing GoogleGenerativeAI for blog generation (last-resort)")
                        return GoogleGenerativeAI(model=llm_model, temperature=llm_temp, google_api_key=ga_key)
                except Exception as e:
                    logger.debug("GoogleGenerativeAI unavailable: %s", e)

                return None

            llm = _get_preferred_llm()
            require_llm = os.getenv("BLOG_REQUIRE_LLM", "false").lower() in ("1", "true", "yes")
            if not llm:
                msg = "No LLM provider available (Mistral, Hugging Face, or Google)"
                logger.warning(msg)
                if require_llm:
                    raise RuntimeError(msg)
                # otherwise allow existing template fallback path by raising to outer handler
                raise RuntimeError(msg)

            import json as _json
            past_posts_json = _get_recent_posts_for_prompt(limit=6)

            business_profile = _load_business_profile()

            prompt = _json.dumps({
                "topic": topic,
                "trend_data": (trend_data or ""),
                "affiliate_links": {k: v for k, v in AFFILIATE_LINKS.items()},
                "our_recent_posts": _json.loads(past_posts_json),
                "business_profile": business_profile
            })

            generation_prompt = f"""
You are an expert content marketer and long-form copywriter for FDWA (Futurist Digital Wealth Agency).

Input (JSON): {prompt}

Task: 1) Analyze the `our_recent_posts` examples and the `trend_data`. Identify patterns that likely drove engagement (hooks, CTAs, examples, statistics, tone, length). 2) Produce a conversion-focused, data-driven, long-form blog post in HTML format that improves on our past posts using those high-performing patterns.

REQUIREMENTS:
- Output MUST be valid JSON only, with keys: "title" (string), "html" (string), "excerpt" (string), "rationale" (short list of 3 improvements made based on our past posts).
- The "html" field must contain well-structured HTML (headings <h1>/<h2>/<h3>, paragraphs, numbered steps, examples/case-studies, bullet lists) and include at least 700 words.
- Explicitly reference one or two data points from `trend_data` when available; if no concrete numbers exist, provide conservative estimates and label them as estimates.
- Include 2 short actionable examples or mini case-studies showing how a reader can apply the advice.
- End with a persuasive CTA that points to https://fdwa.site and an invitation to schedule a consultation.
- Embed exactly 3 recommended affiliate tools (use links from affiliate_links) inside the HTML.
- Provide an "excerpt" (1-2 sentence hook) suitable for social sharing.
- Provide a small JSON array `rationale` (3 items) explaining which past-post patterns were used and why.
- Tone: authoritative, helpful, conversational. Active voice. No filler or vague platitudes.

Return ONLY the JSON. Do NOT include any explanatory text.
"""

            response = llm.invoke(generation_prompt)
            response_text = response.strip()

            # Try to parse JSON from model output
            try:
                parsed = _json.loads(response_text)
                title = parsed.get("title")
                html_output = parsed.get("html")
                excerpt = parsed.get("excerpt", "")

                # If title/html present and not duplicate, return immediately
                if title and html_output and not _is_duplicate_post(title, excerpt or html_output[:200], topic):
                    image_html = ""
                    image_url = image_path or os.environ.get("BLOG_IMAGE_URL")
                    if image_url and image_url.startswith(('http://', 'https://')):
                        image_html = f'<img src="{image_url}" alt="Blog Image" style="max-width:100%;border-radius:12px;margin-bottom:20px;display:block;" />\n'

                    blog_html = image_html + html_output
                    logger.info("LLM-generated blog created: %s", title)
                    return {
                        "blog_html": blog_html,
                        "title": title,
                        "topic": topic,
                        "intro_paragraph": excerpt,
                        "image_url": image_url
                    }
            except Exception as llm_parse_exc:
                logger.exception("LLM output parsing failed: %s", llm_parse_exc)
                if require_llm:
                    raise
        except Exception as llm_exc:
            # Respect BLOG_REQUIRE_LLM: re-raise if set, otherwise continue to template fallback
            require_llm = os.getenv("BLOG_REQUIRE_LLM", "false").lower() in ("1", "true", "yes")
            logger.exception("LLM blog generation failed: %s", llm_exc)
            if require_llm:
                raise

        # Fallback: Try each variation until we find one that hasn't been sent recently
        random.shuffle(variations)  # Randomize order for variety
        
        selected_content = None
        for content in variations:
            if not _is_duplicate_post(content["title"], content["intro_paragraph"], topic):
                selected_content = content
                break
        
        # If all variations have been used, force rotation to different topic
        if not selected_content:
            logger.warning("All %s variations used recently, rotating to different topic", topic)
            all_topics = ["ai", "marketing", "finance", "general"]
            all_topics.remove(topic)
            
            for alt_topic in all_topics:
                alt_variations = content_variations.get(alt_topic, [])
                random.shuffle(alt_variations)
                for content in alt_variations:
                    if not _is_duplicate_post(content["title"], content["intro_paragraph"], alt_topic):
                        selected_content = content
                        topic = alt_topic
                        break
                if selected_content:
                    break
        
        # Last resort: pick random content anyway (shouldn't happen with enough variations)
        if not selected_content:
            logger.warning("No unique content found, selecting random variation")
            selected_content = random.choice(variations)
        
        template = get_template_by_topic(topic)

        # Add image using direct URL (not CID - Composio doesn't support MIME attachments)
        image_html = ""
        image_url = image_path or os.environ.get("BLOG_IMAGE_URL")
        if image_url and image_url.startswith(('http://', 'https://')):
            # Use the actual image URL directly in the HTML
            image_html = f'<img src="{image_url}" alt="Blog Image" style="max-width:100%;border-radius:12px;margin-bottom:20px;display:block;" />\n'
            logger.info("Adding image URL to blog HTML: %s", image_url[:60])

        # Fill in the template
        blog_html = image_html + template.format(
            title=selected_content["title"],
            intro_paragraph=selected_content["intro_paragraph"],
            main_content_header=selected_content["main_content_header"],
            main_content=selected_content["main_content"],
            **AFFILIATE_LINKS
        )

        logger.info("Blog content generated successfully: %s", selected_content["title"])
        return {
            "blog_html": blog_html,
            "title": selected_content["title"],
            "topic": topic,
            "intro_paragraph": selected_content["intro_paragraph"],
            "image_url": image_url  # Return image URL for reference
        }

    except Exception as e:
        logger.exception("Error generating blog content: %s", e)
        return {"error": str(e)}

def send_blog_email(blog_html: str, title: str, image_url: Optional[str] = None) -> Dict[str, Any]:
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


def generate_and_send_blog(trend_data: str = None, image_url: Optional[str] = None) -> Dict[str, Any]:
    """Main function to generate blog content and send via email.
    
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
        fallback_trends = [
            "AI automation trends show 300% increase in small business adoption. Workflow automation saves 15+ hours per week.",
            "Digital product sales are booming in 2025, with entrepreneurs earning passive income from ebooks and guides.",
            "Credit repair with AI is helping thousands improve their scores faster than ever before.",
            "Business automation tools are saving SMBs 20+ hours per week and increasing revenue.",
            "Financial empowerment through tech: more people are using AI to manage money and build wealth.",
            "Social media marketing strategies are evolving with AI-powered content creation tools.",
            "Entrepreneurs are building multiple income streams through digital products and automation.",
            "The gig economy is transforming with AI tools that help freelancers scale their businesses."
        ]
        trend_data = random.choice(fallback_trends)

    # Generate blog content with image URL embedded in HTML
    blog_result = generate_blog_content(trend_data, image_path=image_source)

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