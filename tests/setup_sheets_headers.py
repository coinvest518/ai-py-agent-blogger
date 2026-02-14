"""Set up headers in Google Sheets (run once for new/blank sheets)."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.agent.sheets_agent import setup_sheets_headers

print("=== Setting Up Google Sheets Headers ===\n")

results = setup_sheets_headers()

print(f"\nResults:")
print(f"  Posts sheet: {'✅ Success' if results.get('posts') else '❌ Failed'}")
print(f"  Tokens sheet: {'✅ Success' if results.get('tokens') else '❌ Failed'}")

if all(results.values()):
    print("\n✅ Both sheets are ready! You can now save and search data.")
else:
    print("\n⚠️ Some headers failed to set up. Check the logs above.")

print("\n=== Setup Complete ===")
