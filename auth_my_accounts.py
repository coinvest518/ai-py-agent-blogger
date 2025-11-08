"""Authenticate your personal accounts with Composio.

This script helps you connect your own Gmail, GitHub, etc. accounts.
"""

import os

from composio import Composio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    print("\nAvailable tools to connect:")
    print("1. Gmail")
    print("2. GitHub") 
    print("3. Slack")
    print("4. Google Calendar")
    print("5. All of the above")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    toolkit_map = {
        "1": ["gmail"],
        "2": ["github"],
        "3": ["slack"],
        "4": ["googlecalendar"],
        "5": ["gmail", "github", "slack", "googlecalendar"],
    }
    
    toolkits = toolkit_map.get(choice, ["gmail"])
    
    print(f"\nConnecting toolkits: {', '.join(toolkits)}")
    print("=" * 50)
    
    for toolkit in toolkits:
        try:
            print(f"\nConnecting {toolkit.upper()}...")
            
            # Create connection
            connection_request = composio.toolkits.authorize(
                user_id=user_id, toolkit=toolkit
            )
            
            print("\nOPEN THIS URL IN YOUR BROWSER:")
            print(f"{connection_request.redirect_url}")
            print("\nAfter authorizing, come back here...")
            
            input("Press Enter after completing authorization...")
            
            # Wait for connection
            connection_request.wait_for_connection()
            print(f"SUCCESS: {toolkit.upper()} connected!")
            
        except Exception as e:
            print(f"ERROR connecting {toolkit}: {e}")
    
    print(f"\nDone! Your accounts are connected for user: {user_id}")
    print("You can now use these tools in your agent.")

if __name__ == "__main__":
    authenticate_my_accounts()