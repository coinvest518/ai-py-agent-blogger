"""Debug Google Sheets search to see raw response."""
import sys
import os
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.agent.sheets_agent import GoogleSheetsAgent

agent = GoogleSheetsAgent()

print("=== Debug: Raw Google Sheets Response ===\n")

# First, save a test post
print("1. Saving test post...")
save_result = agent.save_post(
    platform='debug_test',
    content='Debug test post for verification',
    post_id='debug001',
    image_url='',
    metadata={'engagement': '0'}
)
print(f"   Save result: {save_result}\n")

# Wait a moment for API sync
print("2. Waiting 2 seconds for API sync...")
time.sleep(2)

# Now try to read back
print("3. Reading posts sheet...")
response = agent._execute_tool(
    "GOOGLESHEETS_BATCH_GET",
    {
        "spreadsheet_id": agent.posts_sheet_id,
        "ranges": ["Sheet1!A1:I10"]  # Read header + first few rows
    }
)

print(f"\n   Response successful: {response.get('successful')}")
print(f"   Response keys: {response.keys()}")

if not response.get('successful'):
    print(f"\n   ❌ ERROR: {response.get('error')}")
    print(f"   Error data: {response.get('data')}")

if response.get("data"):
    print(f"\n   Data keys: {response['data'].keys()}")
    
    if "valueRanges" in response['data']:
        value_ranges = response['data']['valueRanges']
        print(f"   Number of valueRanges: {len(value_ranges)}")
        
        if value_ranges:
            print(f"   First valueRange keys: {value_ranges[0].keys()}")
            
            if "values" in value_ranges[0]:
                values = value_ranges[0]['values']
                print(f"   Number of rows: {len(values)}")
                
                for i, row in enumerate(values[:5]):  # Show first 5 rows
                    print(f"   Row {i}: {row}")

print("\n=== Debug Complete ===")
