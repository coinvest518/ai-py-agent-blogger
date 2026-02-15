#!/usr/bin/env python3
"""
Direct test of Pollinations.ai API to check if HTTP 522 is resolved.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLLINATIONS_API_KEY")
print(f"Using API Key: {API_KEY[:20]}..." if API_KEY else "No API key found!")

url = "https://gen.pollinations.ai/image/a%20cute%20cat%20sitting%20on%20a%20laptop"
params = {
    "model": "flux",
    "width": 512,
    "height": 512,
    "seed": 42
}
headers = {
    "Authorization": f"Bearer {API_KEY}"
}

print("\n" + "="*70)
print("🧪 TESTING POLLINATIONS.AI DIRECTLY")
print("="*70)
print(f"URL: {url}")
print(f"Model: flux")
print(f"Size: 512x512")
print(f"Headers: Authorization: Bearer {API_KEY[:15]}...")
print("\n⏳ Sending request...")

try:
    response = requests.get(url, params=params, headers=headers, timeout=30)
    
    print(f"\n📡 HTTP Status: {response.status_code}")
    print(f"⏱️  Response Time: {response.elapsed.total_seconds():.2f}s")
    print(f"📦 Content-Type: {response.headers.get('content-type', 'unknown')}")
    print(f"📏 Content Size: {len(response.content)} bytes")
    
    if response.status_code == 200:
        # Save the image
        output_path = "test_pollinations_cat.jpg"
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"\n✅ SUCCESS! Image saved to: {output_path}")
        print(f"   Open it to verify: start {output_path}")
    elif response.status_code == 522:
        print(f"\n❌ HTTP 522: Pollinations server still having issues (timeout)")
        print(f"   This is a temporary server problem on their end")
    elif response.status_code == 401:
        print(f"\n❌ HTTP 401: Invalid API key")
        print(f"   Check your POLLINATIONS_API_KEY in .env")
    elif response.status_code == 402:
        print(f"\n❌ HTTP 402: Out of pollen credits")
        print(f"   Get more at: https://pollinations.ai")
    else:
        print(f"\n❌ FAIL: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print(f"\n❌ TIMEOUT: Request took longer than 30 seconds")
    print(f"   Pollinations server might be slow or down")
except requests.exceptions.ConnectionError as e:
    print(f"\n❌ CONNECTION ERROR: {e}")
    print(f"   Check internet connection or Pollinations status")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
