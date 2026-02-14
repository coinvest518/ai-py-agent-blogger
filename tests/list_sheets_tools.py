import os
import requests
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

print("Listing all GOOGLESHEETS tools available via Composio v3 API...")
print("=" * 60)

try:
    url = "https://backend.composio.dev/api/v3/tools"
    headers = {"x-api-key": COMPOSIO_API_KEY}
    
    resp = requests.get(url, headers=headers, params={"limit": 500}, timeout=30)
    resp.raise_for_status()
    
    data = resp.json()
    print(f"API Response keys: {list(data.keys())}")
    
    tools = data.get("tools", data.get("items", []))
    print(f"Total tools returned: {len(tools)}")
    
    if tools:
        print(f"\nFirst tool structure: {tools[0]}\n")
    
    sheets_tools = []
    for t in tools:
        slug = t.get('slug', t.get('name', t.get('slug_name', '')))
        toolkit = t.get('toolkit', {})
        toolkit_slug = toolkit.get('slug', '') if isinstance(toolkit, dict) else ''
        
        if 'GOOGLESHEETS' in str(slug).upper() or 'googlesheets' in str(toolkit_slug).lower():
            sheets_tools.append(t)
    
    print(f"Found {len(sheets_tools)} Google Sheets tools:\n")
    
    for tool in sheets_tools:
        slug = tool.get('slug', tool.get('name', tool.get('slug_name')))
        name = tool.get('name', tool.get('display_name', ''))
        print(f"  {slug}")
        if name and name != slug:
            print(f"    →{name[:80]}")
        print()
    
    if not sheets_tools:
        print("No Google Sheets tools found. Try searching for 'google' in toolkit:")
        google_tools = [t for t in tools if 'google' in str(t.get('toolkit', {})).lower()]
        print(f"Found {len(google_tools)} tools with 'google' in toolkit")
        for gt in google_tools[:10]:
            print(f"  {gt.get('slug')} (toolkit: {gt.get('toolkit', {}).get('slug')})")

        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

