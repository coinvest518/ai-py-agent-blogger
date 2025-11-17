"""Test the blog email node directly."""

import logging
from src.agent.graph import generate_blog_email_node

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_blog_node():
    """Test the blog email node functionality."""
    logger.info("Testing blog email node...")
    
    # Mock state with trend data
    mock_state = {
        "trend_data": "AI automation trends show 300% increase in small business adoption. Marketing automation saves time and increases leads."
    }
    
    try:
        result = generate_blog_email_node(mock_state)
        
        logger.info("Blog Node Results:")
        logger.info("Blog Status: %s", result.get("blog_status", "N/A"))
        logger.info("Blog Title: %s", result.get("blog_title", "N/A"))
        
        if "Failed" not in result.get("blog_status", ""):
            print("Blog node test PASSED")
            return True
        else:
            print("Blog node test FAILED")
            return False
            
    except Exception as e:
        logger.exception("Blog node test failed: %s", e)
        print("Blog node test FAILED with exception")
        return False

if __name__ == "__main__":
    success = test_blog_node()
    if success:
        print("\nSUCCESS: Blog email node is working in the agent workflow!")
    else:
        print("\nFAILED: Blog email node needs debugging.")