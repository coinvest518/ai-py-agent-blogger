"""Composio setup and tool authorization script.

Run this script to authorize tools and set up connections.
"""

import os

from composio import Composio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def setup_composio_tools() -> None:
    """Set up Composio tools and authorize connections."""
    # Initialize Composio
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        msg = "ERROR: COMPOSIO_API_KEY not found in .env file"
        raise ValueError(msg)
    
    composio = Composio(api_key=api_key)
    
    user_id = "user@example.com"  # Replace with actual user ID
    
    # Available toolkits to authorize
    available_toolkits = ["gmail", "github", "slack", "calendar"]
    
    print("Composio Tool Setup")
    print("=" * 50)
    
    for toolkit in available_toolkits:
        try:
            print(f"\nSetting up {toolkit.upper()} toolkit...")
            
            # Initialize connection request
            connection_request = composio.toolkits.authorize(
                user_id=user_id, 
                toolkit=toolkit
            )
            
            print(f"Visit the URL to authorize {toolkit}:")
            print(f"URL: {connection_request.redirect_url}")
            
            # Wait for user input to continue
            input(f"Press Enter after authorizing {toolkit}...")
            
            # Wait for the connection to be active
            connection_request.wait_for_connection()
            print(f"SUCCESS: {toolkit.upper()} authorized!")
            
        except Exception as e:
            print(f"ERROR setting up {toolkit}: {e}")
    
    print("\nComposio setup complete!")
    print("You can now use these tools in your LangGraph agent.")

if __name__ == "__main__":
    setup_composio_tools()