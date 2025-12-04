"""Blog Email Agent for FDWA AI Automation Agency.

This agent generates blog content using predefined templates and sends it via Gmail.
"""

import base64
import hashlib
import json
import logging
import os
import random
import requests
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
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
    """Load the record of sent blog posts."""
    if SENT_POSTS_FILE.exists():
        try:
            with open(SENT_POSTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"sent_titles": [], "sent_hashes": [], "last_topics": []}


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


def _record_sent_post(title: str, content: str, topic: str) -> None:
    """Record a sent post to prevent future duplicates."""
    sent_data = _load_sent_posts()
    content_hash = _get_content_hash(title, content)
    
    # Add to tracking lists (keep last 50 items max)
    sent_data.setdefault("sent_titles", []).append(title)
    sent_data["sent_titles"] = sent_data["sent_titles"][-50:]
    
    sent_data.setdefault("sent_hashes", []).append(content_hash)
    sent_data["sent_hashes"] = sent_data["sent_hashes"][-50:]
    
    sent_data.setdefault("last_topics", []).append(topic)
    sent_data["last_topics"] = sent_data["last_topics"][-10:]
    
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


def generate_blog_content(trend_data: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate blog content using predefined templates with duplicate prevention."""
    logger.info("---GENERATING BLOG CONTENT---")

    # Remove any error or search system text from trend_data
    for bad in ["SERPAPI_SEARCH:", "TAVILY_SEARCH:", "Account out of searches", "error", "limit"]:
        if bad.lower() in trend_data.lower():
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
        
        # Try each variation until we find one that hasn't been sent recently
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

        # Add image placeholder for CID reference (will be replaced with embedded image)
        image_html = ""
        if image_path or os.environ.get("BLOG_IMAGE_PATH") or os.environ.get("BLOG_IMAGE_URL"):
            # Use CID reference for embedded image in email
            image_html = '<img src="cid:blog_image" alt="Blog Image" style="max-width:100%;border-radius:12px;margin-bottom:20px;" />\n'

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
            "intro_paragraph": selected_content["intro_paragraph"]
        }

    except Exception as e:
        logger.exception("Error generating blog content: %s", e)
        return {"error": str(e)}


def _download_image(image_source: str) -> Optional[bytes]:
    """Download image from URL or read from local path.
    
    Args:
        image_source: URL or local file path of the image.
        
    Returns:
        Image bytes or None if failed.
    """
    try:
        if image_source.startswith(('http://', 'https://')):
            # Download from URL
            response = requests.get(image_source, timeout=30)
            response.raise_for_status()
            logger.info("Downloaded image from URL: %s", image_source[:50])
            return response.content
        elif os.path.exists(image_source):
            # Read from local file
            with open(image_source, 'rb') as f:
                logger.info("Read image from local path: %s", image_source)
                return f.read()
        else:
            logger.warning("Image source not found: %s", image_source)
            return None
    except Exception as e:
        logger.error("Failed to get image: %s", e)
        return None


def _get_image_mime_type(image_path: str) -> str:
    """Determine MIME type from file extension."""
    ext = image_path.lower().split('.')[-1] if '.' in image_path else 'jpeg'
    mime_map = {
        'jpg': 'jpeg',
        'jpeg': 'jpeg',
        'png': 'png',
        'gif': 'gif',
        'webp': 'webp'
    }
    return mime_map.get(ext, 'jpeg')


def send_blog_email(blog_html: str, title: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Send blog content via Gmail with optional embedded image.
    
    Args:
        blog_html: HTML content of the blog post.
        title: Subject/title of the email.
        image_path: Optional path or URL to image to embed.
        
    Returns:
        Dictionary with email status.
    """
    logger.info("---SENDING BLOG EMAIL---")
    
    try:
        blogger_email = os.getenv("BLOGGER_EMAIL", "mildhighent.moneyovereverything@blogger.com")
        
        # Get image from various sources
        image_source = image_path or os.environ.get("BLOG_IMAGE_PATH") or os.environ.get("BLOG_IMAGE_URL")
        image_data = None
        
        if image_source:
            image_data = _download_image(image_source)
            if image_data:
                logger.info("Image loaded successfully (%d bytes)", len(image_data))
        
        # If we have image data, we need to create a proper MIME message with embedded image
        if image_data:
            logger.info("Sending email with embedded image attachment")
            
            # Create multipart/related message for inline images
            msg = MIMEMultipart('related')
            msg['Subject'] = title
            msg['To'] = blogger_email
            
            # Create the HTML part with CID reference
            html_part = MIMEText(blog_html, 'html')
            
            # Create alternative container to hold HTML
            msg_alternative = MIMEMultipart('alternative')
            msg_alternative.attach(html_part)
            msg.attach(msg_alternative)
            
            # Attach the image with Content-ID
            mime_type = _get_image_mime_type(image_source)
            img = MIMEImage(image_data, _subtype=mime_type)
            img.add_header('Content-ID', '<blog_image>')
            img.add_header('Content-Disposition', 'inline', filename='blog_image.jpg')
            msg.attach(img)
            
            # Convert to raw base64 for Gmail API
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            # Send via Gmail API with raw message
            email_params = {
                "recipient_email": blogger_email,
                "subject": title,
                "body": blog_html,
                "is_html": True,
                "user_id": "me",
                "raw": raw_message  # Include raw MIME message if API supports it
            }
        else:
            logger.info("Sending email without image (no image available)")
            # Remove CID reference if no image available
            blog_html = blog_html.replace('<img src="cid:blog_image" alt="Blog Image" style="max-width:100%;border-radius:12px;margin-bottom:20px;" />\n', '')
            
            email_params = {
                "recipient_email": blogger_email,
                "subject": title,
                "body": blog_html,
                "is_html": True,
                "user_id": "me"
            }
        
        # Send email using Composio Gmail
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
                "has_image": image_data is not None
            }
        else:
            # If raw message failed, try fallback with image URL in HTML
            if image_data and image_source and image_source.startswith('http'):
                logger.info("Raw message failed, trying fallback with image URL")
                blog_html_with_url = blog_html.replace(
                    'src="cid:blog_image"', 
                    f'src="{image_source}"'
                )
                fallback_params = {
                    "recipient_email": blogger_email,
                    "subject": title,
                    "body": blog_html_with_url,
                    "is_html": True,
                    "user_id": "me"
                }
                fallback_response = composio_client.tools.execute(
                    "GMAIL_SEND_EMAIL",
                    fallback_params,
                    connected_account_id=os.getenv("GMAIL_CONNECTED_ACCOUNT_ID")
                )
                if fallback_response.get("successful", False):
                    logger.info("Fallback email with URL sent successfully!")
                    return {
                        "email_status": "Sent successfully (image linked)", 
                        "recipient": blogger_email,
                        "has_image": True
                    }
            
            error_msg = email_response.get("error", "Unknown error")
            logger.error("Gmail send failed: %s", error_msg)
            return {"email_status": f"Failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Email sending failed: %s", e)
        return {"email_status": f"Failed: {str(e)}"}


def generate_and_send_blog(trend_data: str = None, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Main function to generate blog content and send via email.
    
    Args:
        trend_data: Trend data to use for content generation.
        image_path: Optional path or URL to image to include.
        
    Returns:
        Dictionary with blog and email status.
    """
    logger.info("Starting blog generation and email process...")
    
    # Get image path from various sources
    image_source = image_path or os.environ.get("BLOG_IMAGE_PATH") or os.environ.get("BLOG_IMAGE_URL")
    
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

    # Generate blog content
    blog_result = generate_blog_content(trend_data, image_path=image_source)

    if "error" in blog_result:
        return blog_result

    # Send email with image
    email_result = send_blog_email(
        blog_result["blog_html"], 
        blog_result["title"],
        image_path=image_source
    )

    # Record the sent post to prevent future duplicates
    if email_result.get("email_status", "").startswith("Sent"):
        _record_sent_post(
            blog_result["title"], 
            blog_result.get("intro_paragraph", ""),
            blog_result["topic"]
        )
        logger.info("Recorded sent post to prevent duplicates: %s", blog_result["title"])

    # Combine results
    return {
        "blog_title": blog_result["title"],
        "blog_topic": blog_result["topic"],
        "email_status": email_result["email_status"],
        "recipient": email_result.get("recipient", ""),
        "has_image": email_result.get("has_image", False),
        "blog_html_preview": blog_result["blog_html"][:200] + "..."
    }