"""Test script for blog email agent functionality."""

import logging
import os
from dotenv import load_dotenv
from src.agent.blog_email_agent import generate_and_send_blog

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_blog_email():
    """Test the blog email generation and sending functionality."""
    logger.info("Starting blog email test...")
    
    # Sample trend data for testing
    test_trend_data = """
    AI automation trends show 300% increase in small business adoption. 
    Workflow automation saves 15+ hours per week for service businesses.
    SMB owners report 40% revenue increase after implementing AI systems.
    Customer service automation reduces response time by 80%.
    """
    
    try:
        # Test the blog generation and email sending
        result = generate_and_send_blog(test_trend_data)
        
        logger.info("Test Results:")
        logger.info("Blog Title: %s", result.get("blog_title", "N/A"))
        logger.info("Blog Topic: %s", result.get("blog_topic", "N/A"))
        logger.info("Email Status: %s", result.get("email_status", "N/A"))
        logger.info("Recipient: %s", result.get("recipient", "N/A"))
        logger.info("Blog Preview: %s", result.get("blog_html_preview", "N/A"))
        
        if "Failed" in result.get("email_status", ""):
            logger.error("Blog email test failed!")
            return False
        else:
            logger.info("Blog email test completed successfully!")
            return True
            
    except Exception as e:
        logger.exception("Blog email test failed with exception: %s", e)
        return False

if __name__ == "__main__":
    success = test_blog_email()
    if success:
        print("\nBlog email test PASSED")
    else:
        print("\nBlog email test FAILED")