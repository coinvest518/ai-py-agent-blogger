"""Simple test for blog email functionality using templates directly."""

import logging
import os
from dotenv import load_dotenv
from composio import Composio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Composio client
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id="default"
)

def test_simple_blog_email():
    """Test sending a simple blog email using predefined content."""
    logger.info("Starting simple blog email test...")
    
    # Simple blog content using the AI template
    blog_title = "AI Automation Transforms Small Business Operations"
    
    blog_html = """<h1>AI Automation Transforms Small Business Operations</h1>

<p>Smart entrepreneurs are discovering that AI automation isn't just for tech giants anymore. Small and medium businesses are leveraging intelligent workflows to eliminate manual tasks, reduce operational costs, and scale their operations without hiring additional staff.</p>

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
  <li><strong>Website & Hosting:</strong> <a href="https://hostinger.com?ref=fdwa" target="_blank">Hostinger</a> - Professional hosting that scales with your business</li>
  <li><strong>AI App Development:</strong> <a href="https://lovable.dev?ref=fdwa" target="_blank">Lovable</a> - Build apps without coding</li>
  <li><strong>Business Communication:</strong> <a href="https://openphone.com?ref=fdwa" target="_blank">OpenPhone</a> - Professional phone system</li>
  <li><strong>Content Creation:</strong> <a href="https://veed.io?ref=fdwa" target="_blank">Veed</a> - AI video editing made simple</li>
  <li><strong>Voice AI:</strong> <a href="https://elevenlabs.io?ref=fdwa" target="_blank">ElevenLabs</a> - Professional AI voice generation</li>
</ul>

<h2>The ROI of AI Automation</h2>
<p>Businesses implementing AI automation report average time savings of 15+ hours per week and revenue increases of 40% within the first year. From automated customer service to intelligent lead qualification, AI systems work 24/7 to grow your business while you focus on strategy and growth.</p>

<h2>Start Your AI Transformation Today</h2>
<p>The businesses that adopt AI automation now will dominate their markets tomorrow. Don't wait - your competitors are already getting ahead.</p>

<p><strong>Ready to scale your business with AI?</strong> Visit <a href="https://fdwa.site" target="_blank">FDWA</a> for expert AI consulting and implementation.</p>

<p><em>Transform your business operations, increase efficiency, and unlock new revenue streams with proven AI strategies.</em></p>

Labels: ai, automation, business, entrepreneurship, fdwa, scaling"""
    
    try:
        # Email configuration
        blogger_email = os.getenv("BLOGGER_EMAIL", "mildhighent.moneyovereverything@blogger.com")
        
        email_params = {
            "recipient_email": blogger_email,
            "subject": blog_title,
            "body": blog_html,
            "is_html": True,
            "user_id": "me"
        }
        
        logger.info("Sending email to: %s", blogger_email)
        logger.info("Subject: %s", blog_title)
        
        # Send email using Gmail
        email_response = composio_client.tools.execute(
            "GMAIL_SEND_EMAIL",
            email_params,
            connected_account_id=os.getenv("GMAIL_CONNECTED_ACCOUNT_ID")
        )
        
        logger.info("Gmail response: %s", email_response)
        
        if email_response.get("successful", False):
            logger.info("Blog email sent successfully!")
            print("Blog email test PASSED - Email sent successfully!")
            return True
        else:
            error_msg = email_response.get("error", "Unknown error")
            logger.error("Gmail send failed: %s", error_msg)
            print(f"Blog email test FAILED - Gmail error: {error_msg}")
            return False
            
    except Exception as e:
        logger.exception("Email sending failed: %s", e)
        print(f"Blog email test FAILED - Exception: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_simple_blog_email()
    if success:
        print("\nSUCCESS: Blog email functionality is working!")
    else:
        print("\nFAILED: Blog email functionality needs debugging.")