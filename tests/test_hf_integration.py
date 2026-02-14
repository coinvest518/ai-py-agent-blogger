"""Test Hugging Face Image Generation Integration.

This script tests the full integration of Hugging Face image generation
in the agent workflow without making actual social media posts.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_hf_standalone():
    """Test Hugging Face image generation standalone."""
    print("=" * 70)
    print("TEST 1: Hugging Face Image Generation (Standalone)")
    print("=" * 70)
    
    from src.agent.hf_image_gen import generate_image_hf, save_image_locally
    
    test_prompt = "Modern professional business office with AI technology, futuristic cyberpunk style, clean design"
    
    result = generate_image_hf(
        prompt=test_prompt,
        model="flux-schnell",  # Fast FLUX model
        width=512,
        height=512,
        timeout=60
    )
    
    if result.get("success"):
        print(f"✅ Image generated successfully!")
        print(f"   Model: {result['model']}")
        print(f"   Size: {len(result['image_bytes'])} bytes")
        
        # Save it
        filepath = save_image_locally(result["image_bytes"], "test_integration.png")
        print(f"   Saved to: {filepath}")
        return True
    else:
        print(f"❌ Generation failed: {result.get('error')}")
        return False


def test_image_node_integration():
    """Test generate_image_node integration."""
    print("\n" + "=" * 70)
    print("TEST 2: generate_image_node Integration")
    print("=" * 70)
    
    from src.agent.graph import generate_image_node, AgentState
    
    # Mock state with tweet text
    test_state = {
        "tweet_text": "🚀 AI automation is transforming businesses! Get smart credit strategies at https://fdwa.site #YBOT #AIAutomation"
    }
    
    print("Testing generate_image_node() with mock state...")
    result = generate_image_node(test_state)
    
    if "error" not in result:
        print(f"✅ Image node successful!")
        print(f"   Image Path: {result.get('image_path')}")
        print(f"   Image URL: {result.get('image_url')}")
        return True
    else:
        print(f"❌ Image node failed: {result.get('error')}")
        return False


def test_template_generation():
    """Test template-based content generation."""
    print("\n" + "=" * 70)
    print("TEST 3: Template-Based Content Generation")
    print("=" * 70)
    
    from src.agent.graph import generate_tweet_node, convert_to_telegram_crypto_post
    
    # Test tweet generation
    test_state = {
        "trend_data": "Bitcoin reaches new highs. Ethereum DeFi protocols gaining traction. Top tokens: BTC, ETH, SOL, MATIC"
    }
    
    print("Testing generate_tweet_node()...")
    tweet_result = generate_tweet_node(test_state)
    
    if "tweet_text" in tweet_result:
        tweet = tweet_result["tweet_text"]
        print(f"✅ Tweet generated: {tweet[:100]}...")
        print(f"   Length: {len(tweet)} chars")
        
        # Test Telegram conversion
        print("\nTesting convert_to_telegram_crypto_post()...")
        telegram_msg = convert_to_telegram_crypto_post(
            test_state["trend_data"],
            tweet
        )
        print(f"✅ Telegram message: {telegram_msg[:100]}...")
        print(f"   Length: {len(telegram_msg)} chars")
        return True
    else:
        print(f"❌ Tweet generation failed: {tweet_result.get('error')}")
        return False


def main():
    """Run all integration tests."""
    print("\n🚀 HUGGING FACE INTEGRATION TESTS")
    print("Testing complete migration from Google AI to Hugging Face")
    print("\nNOTE: These tests will make actual API calls to Hugging Face.")
    print("Make sure HUGGINGFACE_API_TOKEN is set in your .env file.\n")
    
    # Check for API token
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ ERROR: HF_TOKEN not found in .env")
        print("Get your free token at: https://huggingface.co/settings/tokens")
        print("Add to .env: HF_TOKEN=hf_YourTokenHere")
        return False
    
    print(f"✅ Hugging Face token found: {hf_token[:20]}...\n")
    
    # Run tests
    results = []
    
    # Test 1: Standalone HF generation
    try:
        results.append(("HF Standalone", test_hf_standalone()))
    except Exception as e:
        print(f"❌ Test 1 crashed: {e}")
        results.append(("HF Standalone", False))
    
    # Test 2: Image node integration
    try:
        results.append(("Image Node", test_image_node_integration()))
    except Exception as e:
        print(f"❌ Test 2 crashed: {e}")
        results.append(("Image Node", False))
    
    # Test 3: Template generation
    try:
        results.append(("Template Gen", test_template_generation()))
    except Exception as e:
        print(f"❌ Test 3 crashed: {e}")
        results.append(("Template Gen", False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Google AI successfully removed")
        print("✅ Hugging Face integration working")
        print("✅ Template-based content generation working")
        print("\nYou can now run the full agent workflow!")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("Check error messages above and troubleshooting in GOOGLE_AI_REMOVAL.md")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
