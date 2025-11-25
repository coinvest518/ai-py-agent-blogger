"""Blog Email Agent for FDWA AI Automation Agency.

This agent generates blog content using predefined templates and sends it via Gmail.
"""

import logging
import os
import random
from typing import Dict, Any
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


def generate_blog_content(trend_data: str) -> Dict[str, Any]:
    """Generate blog content using predefined templates."""
    logger.info("---GENERATING BLOG CONTENT---")

    # Use predefined content based on trend data keywords
    topic = "general"  # Default to general topic for diversity
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
    
    # Predefined content based on topic
    content_map = {
        "ai": {
            "title": "AI Automation for Credit Repair and Business Success",
            "intro_paragraph": "Smart entrepreneurs are using AI to fix credit issues and automate their businesses. From dispute letter generators to report analyzers, AI tools are revolutionizing how people build wealth and streamline operations.",
            "main_content_header": "Why AI Beats Traditional Methods",
            "main_content": "People using AI for credit repair see results in weeks, not months. Automated dispute systems work 24/7, generating letters that get denials overturned. Business automation saves 20+ hours per week while increasing revenue through passive income streams."
        },
        "marketing": {
            "title": "Digital Product Marketing: Sell Ebooks and Guides Online",
            "intro_paragraph": "Modern entrepreneurs are building passive income by creating and selling digital products. From credit repair guides to business automation templates, digital products provide freedom and financial security.",
            "main_content_header": "Digital Product Success Stories",
            "main_content": "Creators selling digital products report 300% ROI within the first year. From step-by-step guides to automation templates, these products sell themselves once set up. AI helps create content faster and market it effectively."
        },
        "finance": {
            "title": "Credit Repair Hacks and Financial Empowerment",
            "intro_paragraph": "Financial freedom starts with fixing your credit and building wealth strategically. From dispute letters to investment automation, smart people are using proven methods to improve their financial future.",
            "main_content_header": "Credit Repair That Works",
            "main_content": "Successful credit repair involves knowing the laws and using the right tools. AI dispute writers create perfect letters that get results. Combined with passive income strategies, this creates true financial empowerment."
        },
        "general": {
            "title": "Building Wealth with AI and Digital Products",
            "intro_paragraph": "The future belongs to those who embrace technology for financial success. From credit repair automation to passive income creation, AI tools are democratizing wealth building for everyone.",
            "main_content_header": "Your Path to Financial Freedom",
            "main_content": "High-performing individuals use integrated tech stacks for credit repair, business automation, and wealth building. These systems deliver results through time savings, increased efficiency, and passive income generation."
        }
    }
    
    try:
        content = content_map.get(topic, content_map["ai"])
        template = get_template_by_topic(topic)
        
        # Fill in the template
        blog_html = template.format(
            title=content["title"],
            intro_paragraph=content["intro_paragraph"],
            main_content_header=content["main_content_header"],
            main_content=content["main_content"],
            **AFFILIATE_LINKS
        )
        
        logger.info("Blog content generated successfully")
        return {
            "blog_html": blog_html,
            "title": content["title"],
            "topic": topic
        }
        
    except Exception as e:
        logger.exception("Error generating blog content: %s", e)
        return {"error": str(e)}


def send_blog_email(blog_html: str, title: str) -> Dict[str, Any]:
    """Send blog content via Gmail."""
    logger.info("---SENDING BLOG EMAIL---")
    
    try:
        # Email configuration
        blogger_email = os.getenv("BLOGGER_EMAIL", "mildhighent.moneyovereverything@blogger.com")
        
        email_params = {
            "recipient_email": blogger_email,
            "subject": title,
            "body": blog_html,
            "is_html": True,
            "user_id": "me"
        }
        
        # Send email using Gmail
        email_response = composio_client.tools.execute(
            "GMAIL_SEND_EMAIL",
            email_params,
            connected_account_id=os.getenv("GMAIL_CONNECTED_ACCOUNT_ID")
        )
        
        logger.info("Gmail response: %s", email_response)
        
        if email_response.get("successful", False):
            logger.info("Blog email sent successfully!")
            return {"email_status": "Sent successfully", "recipient": blogger_email}
        else:
            error_msg = email_response.get("error", "Unknown error")
            logger.error("Gmail send failed: %s", error_msg)
            return {"email_status": f"Failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Email sending failed: %s", e)
        return {"email_status": f"Failed: {str(e)}"}


def generate_and_send_blog(trend_data: str = None) -> Dict[str, Any]:
    """Main function to generate blog content and send via email."""
    logger.info("Starting blog generation and email process...")
    
    # Use provided trend data or generate some sample data
    if not trend_data:
        trend_data = "AI automation trends show 300% increase in small business adoption. Workflow automation saves 15+ hours per week."
    
    # Generate blog content
    blog_result = generate_blog_content(trend_data)
    
    if "error" in blog_result:
        return blog_result
    
    # Send email
    email_result = send_blog_email(blog_result["blog_html"], blog_result["title"])
    
    # Combine results
    return {
        "blog_title": blog_result["title"],
        "blog_topic": blog_result["topic"],
        "email_status": email_result["email_status"],
        "recipient": email_result.get("recipient", ""),
        "blog_html_preview": blog_result["blog_html"][:200] + "..."
    }