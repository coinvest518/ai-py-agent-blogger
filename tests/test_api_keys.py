import os
from dotenv import load_dotenv

load_dotenv()

def test_mistral():
    try:
        from langchain_mistralai import ChatMistralAI
        key = os.getenv("MISTRAL_API_KEY")
        if not key:
            return "No MISTRAL_API_KEY set"
        llm = ChatMistralAI(model="mistral-large-2512", temperature=0.25, mistral_api_key=key)
        response = llm.invoke("Hello, test message")
        return f"Mistral OK: {response.content[:50]}..."
    except Exception as e:
        return f"Mistral FAILED: {e}"

def test_huggingface():
    try:
        import requests
        key = os.getenv("HF_TOKEN")
        if not key:
            return "No HF_TOKEN set"
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": "HuggingFaceTB/SmolLM3-3B:hf-inference",
            "messages": [{"role": "user", "content": "Hello, test message"}],
            "temperature": 0.25
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return f"HuggingFace OK: {content[:120]}..."
    except Exception as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            return "HuggingFace FAILED: 401 Unauthorized — your HF_TOKEN is invalid or missing Inference permission. Create a token with 'Inference' access and update .env."
        return f"HuggingFace FAILED: {str(e)}"

def test_google():
    try:
        from langchain_google_genai import GoogleGenerativeAI
        key = os.getenv("GOOGLE_AI_API_KEY")
        if not key:
            return "No GOOGLE_AI_API_KEY set"
        llm = GoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.25, google_api_key=key)
        response = llm.invoke("Hello, test message")
        return f"Google OK: {response[:50]}..."
    except Exception as e:
        return f"Google FAILED: {e}"

if __name__ == "__main__":
    print("Testing API keys...")
    print("Mistral:", test_mistral())
    print("HuggingFace:", test_huggingface())
    print("Google:", test_google())