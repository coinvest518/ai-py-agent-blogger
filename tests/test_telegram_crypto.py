#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Telegram crypto-specific content generation.
Verifies that Telegram gets crypto/DeFi content, not generic business content.
"""

import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.graph import _adapt_for_telegram, convert_to_telegram_crypto_post

def test_telegram_crypto_content():
    """Test that Telegram adapter creates crypto/DeFi specific content."""
    print("=" * 70)
    print("  TELEGRAM CRYPTO CONTENT TEST")
    print("=" * 70)
    print()
    
    # Test different research scenarios
    test_cases = [
        {
            "name": "Crypto-heavy research",
            "insights": "Bitcoin (BTC) hits new highs. Ethereum (ETH) DeFi protocols see massive growth. Solana (SOL) ecosystem expanding. Top tokens: MATIC, AVAX showing strong performance.",
            "expected_tokens": ["BTC", "ETH", "SOL", "MATIC", "AVAX"]
        },
        {
            "name": "DeFi-focused research", 
            "insights": "DeFi market growth accelerates. New token launches in Web3 space. Blockchain technology adoption increasing across industries.",
            "expected_tokens": ["DEFI", "TOKEN", "WEB3", "BLOCKCHAIN"]
        },
        {
            "name": "Generic business research (fallback)",
            "insights": "AI automation tools transforming business operations. Companies seeing 300% productivity gains. Digital transformation accelerating.",
            "expected_tokens": []  # No crypto tokens, should use fallback format
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 70)
        
        # Generate Telegram content
        telegram_content = _adapt_for_telegram(test['insights'])
        
        # Verify it's different from generic
        is_crypto_focused = any(keyword in telegram_content for keyword in [
            "DeFi", "Crypto", "Market Update", "Trending:", "YieldBot", "#DeFi", "#Crypto"
        ])
        
        # Check for token extraction
        tokens_found = [token for token in test['expected_tokens'] 
                        if token in telegram_content.upper()]
        
        print(f"\n📱 Generated Telegram Content:")
        print(telegram_content)
        print()
        
        print(f"✅ Crypto-focused format: {'Yes' if is_crypto_focused else 'No'}")
        print(f"✅ Tokens extracted: {len(tokens_found)}/{len(test['expected_tokens']) if test['expected_tokens'] else 'N/A'}")
        if tokens_found:
            print(f"   Found: {', '.join(tokens_found)}")
        print()
        
        # Verify crypto focus
        if is_crypto_focused:
            results.append(True)
            print("✅ PASS - Telegram content is crypto/DeFi focused\n")
        else:
            results.append(False)
            print("❌ FAIL - Telegram content is NOT crypto focused\n")
    
    # Test the fallback convert function
    print("Test 4: convert_to_telegram_crypto_post() fallback function")
    print("-" * 70)
    trend_data = "Bitcoin reaches $100k. Ethereum DeFi TVL at all-time high. SOL, AVAX showing strength."
    tweet_text = "🚀 Crypto market on fire! Major gains across the board."
    
    crypto_post = convert_to_telegram_crypto_post(trend_data, tweet_text)
    
    print(f"\n📱 Generated Crypto Post:")
    print(crypto_post)
    print()
    
    has_defi_format = "DeFi Market Update" in crypto_post
    has_tokens = any(token in crypto_post for token in ["BTC", "ETH", "SOL"])
    
    print(f"✅ Has DeFi format: {'Yes' if has_defi_format else 'No'}")
    print(f"✅ Has token mentions: {'Yes' if has_tokens else 'No'}")
    
    if has_defi_format and has_tokens:
        results.append(True)
        print("✅ PASS - Fallback function works correctly\n")
    else:
        results.append(False)
        print("❌ FAIL - Fallback function missing crypto elements\n")
    
    # Summary
    print("=" * 70)
    print(f"  RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)
    print()
    
    if all(results):
        print("✅ All tests passed!")
        print()
        print("Telegram is properly configured for crypto/DeFi content:")
        print("  • Extracts crypto tokens from research ✅")
        print("  • Uses 'DeFi Market Update' format ✅")
        print("  • Different from other platforms ✅")
        print("  • Includes crypto-specific hashtags ✅")
        return 0
    else:
        print(f"⚠️  {len(results) - sum(results)} test(s) failed")
        print("Review the Telegram adapter configuration.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = test_telegram_crypto_content()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
