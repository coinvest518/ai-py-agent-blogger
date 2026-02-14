import os
from dotenv import load_dotenv
import requests

load_dotenv()

def test_hf():
    key = os.getenv("HF_TOKEN")
    print(f"HF_TOKEN found: {'Yes' if key else 'No'}")
    if key:
        print(f"Token starts with: {key[:10]}...")
    
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "HuggingFaceTB/SmolLM3-3B:hf-inference",
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
        "temperature": 0.25
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    
    print("✅ HuggingFace Inference API working!")
    print(f"Response: {content}")

if __name__ == "__main__":
    try:
        test_hf()
    except Exception as e:
        print(f"❌ HuggingFace test failed: {e}")
        import traceback
        traceback.print_exc()
