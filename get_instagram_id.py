"""Quick script to get Instagram User ID."""

import os
from composio import Composio
from dotenv import load_dotenv

load_dotenv()

composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

try:
    response = composio_client.tools.execute(
        "INSTAGRAM_GET_USER_INFO",
        {},
        connected_account_id="ca_J8db7D84W8m6",
    )
    
    print("Instagram User Info Response:")
    print(response)
    
    # Extract user ID
    data = response.get("data", {})
    user_id = data.get("id") or data.get("ig_user_id") or data.get("user_id")
    
    print(f"\nInstagram User ID: {user_id}")
    print(f"\nAdd this to your .env file:")
    print(f"INSTAGRAM_USER_ID={user_id}")
    
except Exception as e:
    print(f"Error: {e}")
