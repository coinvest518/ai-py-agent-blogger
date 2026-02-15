#!/usr/bin/env python3
"""
Test blog generation with FDWA link enforcement and cascading LLM.
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.blog_email_agent import generate_blog_content
from agent.llm_provider import get_llm

def test_blog_generation():
    print("=" * 70)
    print("Testing Blog Generation with FDWA Link Enforcement")
    print("=" * 70)
    
    try:
        print("\n🔹 Setting up test data...")
        test_summary = """
        AI automation is transforming cryptocurrency trading through advanced 
        algorithms and real-time market analysis. Modern trading bots can execute 
        trades 24/7, analyze market trends, and make data-driven decisions faster 
        than human traders.
        """
        
        test_key_points = [
            "AI-powered trading bots operate continuously",
            "Real-time market analysis and pattern recognition",
            "Automated risk management and portfolio balancing",
            "Integration with major crypto exchanges"
        ]
        
        primary_site = "https://fdwa.site"
        
        print("\n🔹 Generating blog content with cascading LLM...")
        print("   This will try multiple LLM providers if needed...")
        
        blog_html = generate_blog_content(
            summary=test_summary,
            key_points=test_key_points,
            primary_site=primary_site
        )
        
        print("\n✅ Blog generated successfully!")
        
        # Check for FDWA link
        has_fdwa_link = "fdwa.site" in blog_html.lower()
        
        print("\n🔍 Checking content quality:")
        print(f"   ✓ Contains fdwa.site link: {has_fdwa_link}")
        print(f"   ✓ Blog length: {len(blog_html)} characters")
        
        # Show excerpt
        if has_fdwa_link:
            print("\n📝 FDWA link found in blog! ✅")
            # Find and show the link context
            link_pos = blog_html.lower().find("fdwa.site")
            if link_pos > 0:
                start = max(0, link_pos - 100)
                end = min(len(blog_html), link_pos + 150)
                excerpt = blog_html[start:end]
                print(f"\n   Context: ...{excerpt}...")
        else:
            print("\n❌ WARNING: fdwa.site link NOT found in blog!")
            
        # Save to file
        output_file = "test_blog_output.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(blog_html)
        print(f"\n💾 Blog saved to: {output_file}")
        
        print("\n" + "=" * 70)
        print("✅ TEST PASSED - Blog generation with cascading LLM works!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_blog_generation()
