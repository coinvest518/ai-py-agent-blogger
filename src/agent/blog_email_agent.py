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

<h2>Why AI Is Transforming Business Operations</h2>
<p>Smart entrepreneurs are leveraging AI automation to:</p>
<ul>
  <li>Eliminate repetitive manual tasks</li>
  <li>Scale operations without hiring more staff</li>
  <li>Improve customer experience through automation</li>
  <li>Generate more revenue with less effort</li>
</ul>

<h2>Essential Tools for AI-Powered Business Growth</h2>
<p>Here are the game-changing tools successful entrepreneurs are using:</p>
<ul>
  <li><strong>Website & Hosting:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Professional hosting that scales with your business</li>
  <li><strong>AI App Development:</strong> <a href="{affiliate_lovable}" target="_blank">Lovable</a> - Build apps without coding</li>
  <li><strong>Business Communication:</strong> <a href="{affiliate_openphone}" target="_blank">OpenPhone</a> - Professional phone system</li>
  <li><strong>Content Creation:</strong> <a href="{affiliate_veed}" target="_blank">Veed</a> - AI video editing made simple</li>
  <li><strong>Voice AI:</strong> <a href="{affiliate_elevenlabs}" target="_blank">ElevenLabs</a> - Professional AI voice generation</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Start Your AI Transformation Today</h2>
<p>The businesses that adopt AI automation now will dominate their markets tomorrow. Don't wait - your competitors are already getting ahead.</p>

<p><strong>Ready to scale your business with AI?</strong> Visit <a href="https://fdwa.site" target="_blank">FDWA</a> for expert AI consulting and implementation.</p>

<p><em>Transform your business operations, increase efficiency, and unlock new revenue streams with proven AI strategies.</em></p>

Labels: ai, automation, business, entrepreneurship, fdwa, scaling"""

TEMPLATE_MARKETING = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>The Digital Marketing Revolution</h2>
<p>Modern businesses are winning with smart digital strategies:</p>
<ul>
  <li>Automated customer acquisition systems</li>
  <li>AI-powered content creation workflows</li>
  <li>Data-driven decision making</li>
  <li>Scalable marketing automation</li>
</ul>

<h2>Must-Have Tools for Digital Growth</h2>
<p>Build your marketing stack with these proven tools:</p>
<ul>
  <li><strong>Chatbot Automation:</strong> <a href="{affiliate_manychat}" target="_blank">ManyChat</a> - Engage customers 24/7</li>
  <li><strong>Workflow Automation:</strong> <a href="{affiliate_n8n}" target="_blank">n8n</a> - Connect all your business tools</li>
  <li><strong>Web Hosting:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Fast, reliable hosting</li>
  <li><strong>Video Marketing:</strong> <a href="{affiliate_veed}" target="_blank">Veed</a> - Create engaging video content</li>
  <li><strong>Data Collection:</strong> <a href="{affiliate_brightdata}" target="_blank">BrightData</a> - Market research and insights</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Scale Your Marketing Impact</h2>
<p>Stop competing on price and start competing on value. Smart marketing automation lets you deliver personalized experiences at scale.</p>

<p>Get professional marketing strategy and implementation at <a href="https://fdwa.site" target="_blank">FDWA</a>.</p>

Labels: marketing, automation, growth, digital, fdwa, strategy"""

TEMPLATE_FINANCIAL = """<h1>{title}</h1>

<p>{intro_paragraph}</p>

<h2>Building Wealth in the Digital Age</h2>
<p>Smart investors and entrepreneurs are diversifying with:</p>
<ul>
  <li>Cryptocurrency and digital assets</li>
  <li>Automated investment strategies</li>
  <li>Digital product revenue streams</li>
  <li>Technology-driven business models</li>
</ul>

<h2>Financial Tools for Modern Entrepreneurs</h2>
<p>Maximize your earning potential with these platforms:</p>
<ul>
  <li><strong>Crypto Rewards:</strong> <a href="{affiliate_cointiply}" target="_blank">Cointiply</a> - Earn cryptocurrency daily</li>
  <li><strong>Financial Management:</strong> <a href="{affiliate_ava}" target="_blank">Ava</a> - Smart money management</li>
  <li><strong>Digital Products:</strong> <a href="{affiliate_theleap}" target="_blank">The Leap</a> - Create and sell digital products</li>
  <li><strong>E-commerce:</strong> <a href="{affiliate_amazon}" target="_blank">Amazon</a> - Everything for your business</li>
  <li><strong>Business Infrastructure:</strong> <a href="{affiliate_hostinger}" target="_blank">Hostinger</a> - Professional web presence</li>
</ul>

<h2>{main_content_header}</h2>
<p>{main_content}</p>

<h2>Your Financial Future Starts Now</h2>
<p>The wealth gap is widening between those who embrace technology and those who don't. Which side will you be on?</p>

<p>Learn advanced wealth-building strategies at <a href="https://fdwa.site" target="_blank">FDWA</a>.</p>

Labels: finance, cryptocurrency, wealth, digital, fdwa, investment"""

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
    "affiliate_hostinger": "https://hostinger.com?ref=fdwa",
    "affiliate_lovable": "https://lovable.dev?ref=fdwa",
    "affiliate_openphone": "https://openphone.com?ref=fdwa",
    "affiliate_veed": "https://veed.io?ref=fdwa",
    "affiliate_elevenlabs": "https://elevenlabs.io?ref=fdwa",
    "affiliate_manychat": "https://manychat.com?ref=fdwa",
    "affiliate_n8n": "https://n8n.io?ref=fdwa",
    "affiliate_brightdata": "https://brightdata.com?ref=fdwa",
    "affiliate_cointiply": "https://cointiply.com?ref=fdwa",
    "affiliate_ava": "https://ava.me?ref=fdwa",
    "affiliate_theleap": "https://theleap.co?ref=fdwa",
    "affiliate_amazon": "https://amazon.com?ref=fdwa"
}


def get_template_by_topic(topic: str) -> str:
    """Select appropriate template based on topic keywords."""
    topic_lower = topic.lower()
    
    if any(word in topic_lower for word in ['ai', 'automation', 'artificial', 'machine learning']):
        return TEMPLATE_AI_BUSINESS
    elif any(word in topic_lower for word in ['marketing', 'social', 'growth', 'digital']):
        return TEMPLATE_MARKETING
    elif any(word in topic_lower for word in ['finance', 'crypto', 'money', 'wealth', 'investment']):
        return TEMPLATE_FINANCIAL
    else:
        return TEMPLATE_GENERAL


def generate_blog_content(trend_data: str) -> Dict[str, Any]:
    """Generate blog content using predefined templates."""
    logger.info("---GENERATING BLOG CONTENT---")

    # Use predefined content based on trend data keywords
    topic = "ai"  # Default to AI topic
    if trend_data:
        topic_lower = trend_data.lower()
        if any(word in topic_lower for word in ['marketing', 'social', 'growth', 'digital']):
            topic = "marketing"
        elif any(word in topic_lower for word in ['finance', 'crypto', 'money', 'wealth']):
            topic = "finance"
        elif any(word in topic_lower for word in ['ai', 'automation', 'artificial']):
            topic = "ai"
        else:
            topic = "general"
    
    # Predefined content based on topic
    content_map = {
        "ai": {
            "title": "AI Automation Transforms Small Business Operations",
            "intro_paragraph": "Smart entrepreneurs are discovering that AI automation isn't just for tech giants anymore. Small and medium businesses are leveraging intelligent workflows to eliminate manual tasks, reduce operational costs, and scale their operations without hiring additional staff.",
            "main_content_header": "The ROI of AI Automation",
            "main_content": "Businesses implementing AI automation report average time savings of 15+ hours per week and revenue increases of 40% within the first year. From automated customer service to intelligent lead qualification, AI systems work 24/7 to grow your business while you focus on strategy and growth."
        },
        "marketing": {
            "title": "Digital Marketing Automation for Small Businesses",
            "intro_paragraph": "Modern small businesses are winning the competition through smart digital marketing automation. By implementing intelligent workflows, businesses can engage customers 24/7, nurture leads automatically, and scale their marketing efforts without increasing their team size.",
            "main_content_header": "Marketing Automation Success Stories",
            "main_content": "Companies using marketing automation see 451% increase in qualified leads and 34% faster sales cycles. From automated email sequences to intelligent chatbots, these tools help small businesses compete with larger competitors while maintaining personal customer relationships."
        },
        "finance": {
            "title": "Financial Technology for Modern Entrepreneurs",
            "intro_paragraph": "Today's entrepreneurs are leveraging financial technology to build wealth and streamline business operations. From cryptocurrency integration to automated invoicing, smart financial tools are helping small businesses optimize cash flow and explore new revenue streams.",
            "main_content_header": "FinTech ROI for Small Business",
            "main_content": "Businesses using modern financial tools report 25% faster payment processing and 60% reduction in administrative overhead. Automated bookkeeping, digital payment systems, and investment platforms are democratizing financial management for entrepreneurs of all sizes."
        },
        "general": {
            "title": "Business Productivity Tools for Entrepreneurs",
            "intro_paragraph": "Successful entrepreneurs understand that productivity isn't about working harder—it's about working smarter. Modern business tools and automation systems help small business owners focus on growth while technology handles routine operations.",
            "main_content_header": "Essential Productivity Systems",
            "main_content": "High-performing businesses use integrated tool stacks that automate workflows, manage customer relationships, and streamline operations. These systems typically deliver 300% ROI within the first year through time savings and improved efficiency."
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