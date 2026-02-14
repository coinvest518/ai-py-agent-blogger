import os
import sys
import logging
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure we can import from src
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from agent.blog_email_agent import generate_blog_content
except ImportError:
    # Try alternate path if running from root
    sys.path.append(os.getcwd())
    from src.agent.blog_email_agent import generate_blog_content

def test_blog_generation():
    print("--- Starting Blog Generation Test ---")
    
    # Force LLM usage
    os.environ["BLOG_REQUIRE_LLM"] = "true"
    
    # We expect this to try Mistral first. If that fails (or key invalid), 
    # it tries HF. If HF fails (quota), it should try Google.
    
    topic = "The Future of AI Agents in 2026"
    trend_data = "AI agents are becoming autonomous and handling complex workflows."
    
    try:
        result = generate_blog_content(trend_data=trend_data, context={"topic": topic})
        
        print("\n✅ Generation SUCCESS!")
        print(f"Title: {result.get('title')}")
        print(f"Word Count (approx): {len(result.get('blog_html', '').split())}")
        
        if result.get("blog_html"):
            with open("test_blog_output.html", "w", encoding="utf-8") as f:
                f.write(result["blog_html"])
            print("Saved output to test_blog_output.html")
            
    except Exception as e:
        print(f"\n❌ Generation FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_blog_generation()
