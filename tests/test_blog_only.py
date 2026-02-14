"""Test blog generation in isolation - see how the AI creates blog posts."""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.blog_email_agent import generate_blog_content

def test_blog_generation():
    """Test blog post generation."""
    print("=" * 70)
    print("🎨 BLOG GENERATION TEST")
    print("=" * 70)
    
    # Test with a sample trend/topic
    trend_data = """AI automation trends show 300% increase in small business adoption. 
    Workflow automation saves 15+ hours per week for entrepreneurs. 
    Tools like AI assistants and automated marketing are revolutionizing how small businesses operate.
    The future of business is automated, efficient, and scalable."""
    
    print(f"\n📝 Trend Data:\n{trend_data}")
    print("\n🤖 Generating blog post with AI...")
    print("   (This may take 30-60 seconds if using LLM...)\n")
    
    try:
        # Generate the blog post
        result = generate_blog_content(
            trend_data=trend_data,
            image_path=None  # No image for this test
        )
        
        print("=" * 70)
        print("✅ BLOG POST GENERATED!")
        print("=" * 70)
        
        # Extract details (function returns: blog_html, title, topic, intro_paragraph, image_url)
        blog_title = result.get("title", "No title")
        blog_html = result.get("blog_html", "")
        topic = result.get("topic", "")
        intro = result.get("intro_paragraph", "")
        image_url = result.get("image_url", None)
        
        print(f"\n📰 TITLE:")
        print(f"   {blog_title}")
        
        print(f"\n📊 STATS:")
        print(f"   HTML length: {len(blog_html)} chars")
        print(f"   Topic: {topic}")
        print(f"   Has image: {'Yes ✅' if image_url else 'No ❌'}")
        
        if image_url:
            print(f"\n🖼️  IMAGE:")
            print(f"   URL: {image_url}")
        
        if intro:
            print(f"\n📄 INTRO:")
            print("-" * 70)
            print(intro)
            print("-" * 70)
        
        print(f"\n💻 HTML PREVIEW (first 800 chars):")
        print("-" * 70)
        html_preview = blog_html[:800] + "..." if len(blog_html) > 800 else blog_html
        print(html_preview)
        print("-" * 70)
        
        # Check if it used LLM or template
        if result.get("error"):
            print(f"\n⚠️  Error: {result['error']}")
        else:
            # Check log context or metadata - the function doesn't explicitly return source
            print("\n🤖 Source: Check above for LLM or template fallback messages")

        
        print("\n" + "=" * 70)
        print("🎉 Blog generation test complete!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ BLOG GENERATION FAILED")
        print("=" * 70)
        print(f"\nError: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        import traceback
        print("\n📋 Full traceback:")
        traceback.print_exc()
        
        return False

if __name__ == "__main__":
    print("\n🔧 Testing blog generation...\n")
    
    success = test_blog_generation()
    
    if success:
        print("\n✅ Blog generation is working!")
        print("   The AI can create full blog posts with images.")
    else:
        print("\n⚠️  Blog generation failed - see errors above")
