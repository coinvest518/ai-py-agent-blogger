"""Authenticate your personal accounts with Composio.

This script helps you connect your own Gmail, GitHub, etc. accounts.
"""

import os

from composio import Composio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import logging
logger = logging.getLogger(__name__)


def authenticate_my_accounts() -> None:
    """Authenticate your personal accounts."""
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        msg = "ERROR: COMPOSIO_API_KEY not found in .env file"
        raise ValueError(msg)
    
    composio = Composio(api_key=api_key)
    
    # Use your email as user_id
    user_id = input("Enter your email address: ").strip()
    
    # Choose which tools to connect
    logger.info("Available tools to connect:")
    logger.info("1. Gmail")
    logger.info("2. GitHub")
    logger.info("3. Slack")
    logger.info("4. Google Calendar")
    logger.info("5. All of the above")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    toolkit_map = {
        "1": ["gmail"],
        "2": ["github"],
        "3": ["slack"],
        "4": ["googlecalendar"],
        "5": ["gmail", "github", "slack", "googlecalendar"],
    }
    
    toolkits = toolkit_map.get(choice, ["gmail"])
    
    logger.info("Connecting toolkits: %s", ", ".join(toolkits))
    logger.info("%s", "=" * 50)
    
    for toolkit in toolkits:
        try:
            logger.info("Connecting %s...", toolkit.upper())
            
            # Create connection
            connection_request = composio.toolkits.authorize(
                user_id=user_id, toolkit=toolkit
            )
            
            logger.info("OPEN THIS URL IN YOUR BROWSER:")
            logger.info("%s", connection_request.redirect_url)
            logger.info("After authorizing, come back here...")
            
            input("Press Enter after completing authorization...")
            
            # Wait for connection
            connection_request.wait_for_connection()
            logger.info("SUCCESS: %s connected!", toolkit.upper())
            
        except Exception as e:
            logger.exception("ERROR connecting %s: %s", toolkit, e)
    
    logger.info("Done! Your accounts are connected for user: %s", user_id)
    logger.info("You can now use these tools in your agent.")

if __name__ == "__main__":
    authenticate_my_accounts()