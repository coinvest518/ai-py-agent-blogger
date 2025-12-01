#!/usr/bin/env python3
"""
Test script to run the full AI agent flow and display results.
This script invokes the autonomous social media agent graph and prints the output.
"""

import asyncio
import logging
from agent.graph import graph

# Set up logging to see the output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_full_flow():
    """Run the complete agent flow and display results."""
    logger.info("Starting full AI agent flow test...")

    # No inputs needed - fully autonomous
    inputs = {}

    try:
        # Run the graph
        result = await graph.ainvoke(inputs)

        # Display results
        print("\n" + "="*60)
        print("AI AGENT EXECUTION RESULTS")
        print("="*60)

        print(f"Tweet Text: {result.get('tweet_text', 'N/A')}")
        print(f"Image URL: {result.get('image_url', 'N/A')}")
        print(f"Twitter URL: {result.get('twitter_url', 'N/A')}")
        print(f"Facebook Status: {result.get('facebook_status', 'N/A')}")
        print(f"LinkedIn Status: {result.get('linkedin_status', 'N/A')}")
        print(f"Instagram Status: {result.get('instagram_status', 'N/A')}")
        print(f"Instagram Comments: {result.get('instagram_comment_status', 'N/A')}")
        print(f"Twitter Reply: {result.get('twitter_reply_status', 'N/A')}")
        print(f"Facebook Comment: {result.get('comment_status', 'N/A')}")
        print(f"Blog Status: {result.get('blog_status', 'N/A')}")
        print(f"Blog Title: {result.get('blog_title', 'N/A')}")

        if result.get("error"):
            print(f"Error: {result.get('error')}")

        print("\n" + "="*60)
        print("EXECUTION COMPLETE")
        print("="*60)

        return result

    except Exception as e:
        logger.exception("Agent execution failed")
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(run_full_flow())