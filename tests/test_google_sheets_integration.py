"""Test Google Sheets integration with crypto token tracking."""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

def test_token_extraction():
    """Test that crypto tokens are extracted from text."""
    from src.agent.sheets_agent import extract_crypto_tokens_from_text
    
    test_cases = [
        ("Check out $BTC and $ETH today!", ["BTC", "ETH"]),
        ("BTCUSDT is pumping! $SOL too", ["BTC", "SOL"]),
        ("No tokens here", []),
        ("$DOGE to the moon! $SHIB following", ["DOGE", "SHIB"]),
    ]
    
    print("\n🧪 Testing Token Extraction:")
    for text, expected in test_cases:
        result = extract_crypto_tokens_from_text(text)
        # Check if all expected tokens are found (order doesn't matter)
        match = set(result) == set(expected)
        status = "✅" if match else "❌"
        print(f"{status} '{text}' -> {result} (expected {expected})")
    

def test_sheets_initialization():
    """Validate Google Sheets IDs are read from .env (no auto-create)."""
    from src.agent.sheets_agent import initialize_google_sheets
    
    print("\n📊 Testing Google Sheets Initialization (validate-only):")
    result = initialize_google_sheets()
    posts_id = result.get('posts_sheet_id')
    tokens_id = result.get('tokens_sheet_id')

    if posts_id and tokens_id:
        print(f"✅ Both spreadsheet IDs present: posts={posts_id} tokens={tokens_id}")
    else:
        print("⚠️ Spreadsheet IDs not both present. Agent will skip Sheets saves until IDs are added to .env.")



def test_save_token():
    """Test saving a token to Google Sheets."""
    from src.agent.sheets_agent import save_token_to_sheets
    
    print("\n💾 Testing Token Save:")
    try:
        save_token_to_sheets(
            symbol="BTC",
            name="Bitcoin",
            source="test_script",
            notes="Test token from integration test"
        )
        print("✅ Token saved successfully")
    except Exception as e:
        print(f"❌ Failed to save token: {e}")


def test_save_post():
    """Test saving a post to Google Sheets."""
    from src.agent.sheets_agent import save_post_to_sheets
    
    print("\n📝 Testing Post Save:")
    try:
        save_post_to_sheets(
            platform="test",
            content="Test post with $BTC mention",
            post_id="test_123",
            metadata={"hash": "abc123def456"}
        )
        print("✅ Post saved successfully")
    except Exception as e:
        print(f"❌ Failed to save post: {e}")


def test_search_posts():
    """Test searching posts in Google Sheets."""
    from src.agent.sheets_agent import search_posts_in_sheets
    
    print("\n🔍 Testing Post Search:")
    try:
        results = search_posts_in_sheets(platform="test", days_back=1)
        print(f"✅ Found {len(results)} test posts")
        if results:
            print(f"   Latest: {results[0]}")
    except Exception as e:
        print(f"❌ Failed to search: {e}")


def test_search_tokens():
    """Test searching tokens in Google Sheets."""
    from src.agent.sheets_agent import search_tokens_in_sheets
    
    print("\n🔍 Testing Token Search:")
    try:
        results = search_tokens_in_sheets(symbol="BTC")
        print(f"✅ Found {len(results)} BTC mentions")
        if results:
            print(f"   Latest: {results[0]}")
    except Exception as e:
        print(f"❌ Failed to search: {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Google Sheets Integration Test Suite")
    print("=" * 60)
    
    # Check if Google Sheets account is configured
    if not os.getenv("GOOGLESHEETS_ACCOUNT_ID"):
        print("❌ GOOGLESHEETS_ACCOUNT_ID not configured in .env")
        print("   Please connect Google Sheets account first.")
        return
    
    print(f"✅ Google Sheets Account: {os.getenv('GOOGLESHEETS_ACCOUNT_ID')}")
    
    # Run tests
    test_token_extraction()
    test_sheets_initialization()
    test_save_token()
    test_save_post()
    test_search_posts()
    test_search_tokens()
    
    print("\n" + "=" * 60)
    print("Test Suite Complete!")
    print("=" * 60)
    print("\n💡 Next Steps:")
    print("   1. Check Google Sheets for saved data")
    print("   2. Run agent with: python main.py")
    print("   3. Monitor for token extraction in logs")
    print("   4. Verify posts saved to Sheets after agent run")


if __name__ == "__main__":
    main()
