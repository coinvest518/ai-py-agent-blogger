"""FDWA Autonomous Twitter AI Agent.

This graph defines a three-step autonomous process:
1. Research trending topics using SERP API
2. Generate strategic FDWA-branded tweet using Google AI
3. Post the tweet to Twitter using Composio
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import TypedDict

from composio import Composio
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAI
from langsmith import traceable
from langgraph.graph import StateGraph

# Load environment variables from .env file
load_dotenv()

# Initialize Composio client
composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

# Configure logging
logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    """Represents the state of our autonomous agent.

    Attributes:
        trend_data: Raw trend data from SERP API.
        insight: Extracted insight aligned with FDWA brand.
        tweet_text: The generated tweet text.
        image_url: The URL of the generated image.
        image_path: The local path of the generated image.
        twitter_url: The URL of the created Twitter post.
        facebook_status: The status of the Facebook post.
        facebook_post_id: The ID of the Facebook post.
        comment_status: The status of the Facebook comment.
        error: To capture any errors that might occur.
    """
    trend_data: str
    insight: str
    tweet_text: str
    image_url: str
    image_path: str
    twitter_url: str
    facebook_status: str
    facebook_post_id: str
    comment_status: str
    error: str


@traceable(name="enhance_image_prompt")
def _enhance_prompt_for_image(text: str) -> str:
    """Convert social media text into a clean visual prompt for image generation.

    Args:
        text: Social media post text with hashtags and formatting.

    Returns:
        Clean, descriptive image prompt optimized for Pollinations AI.
    """
    logger.info("Enhancing image prompt...")

    llm = GoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_AI_API_KEY"),
    )

    prompt = f"""
Convert this social media post into a visual art prompt for AI image generation.

SOCIAL MEDIA TEXT:
{text}

REQUIREMENTS:
- Remove ALL hashtags
- Remove ALL special characters (* # @ etc)
- Remove ALL markdown formatting
- Extract core visual theme
- Add professional business imagery keywords
- Style: modern, clean, professional, futuristic
- Maximum 200 characters

OUTPUT:
Return ONLY the clean image prompt. No explanations.
"""

    try:
        response = llm.invoke(prompt)
        visual_prompt = response.strip()

        # Additional cleanup
        visual_prompt = re.sub(r"[*#@\[\]{}()\'\"\\]", "", visual_prompt)
        visual_prompt = re.sub(r"\s+", " ", visual_prompt).strip()

        logger.info("Enhanced prompt: %s", visual_prompt)
        return visual_prompt

    except Exception as e:
        logger.exception("Error enhancing prompt: %s", e)
        # Fallback: basic cleanup
        fallback = re.sub(r"[*#@\[\]{}()\'\"\\]", "", text)
        fallback = re.sub(r"\s+", " ", fallback).strip()
        return f"Professional business image: {fallback[:150]}"


def research_trends_node(state: AgentState) -> dict:
    """Research trending topics using multiple SERP API tools.

    Args:
        state: Current agent state.

    Returns:
        Dictionary with trend_data or error.
    """
    logger.info("---RESEARCHING TRENDS---")

    # Define search queries for FDWA-relevant topics
    search_queries = [
        "AI automation business",
        "small business growth systems",
        "future of work automation",
        "digital wealth creation",
        "business automation",
    ]

    query = random.choice(search_queries)
    logger.info("Researching: %s", query)

    trend_data = ""

    try:
        # Execute SERP API search
        logger.info("Fetching search results...")
        search_response = composio_client.tools.execute(
            "SERPAPI_SEARCH",
            {"query": query},
            connected_account_id="ca_ibP542LgfMdi",
        )
        trend_data = f"SEARCH: {search_response.get('data', {})!s}"

        logger.info("Trend data collected: %d characters", len(trend_data))
        return {"trend_data": trend_data}

    except Exception as e:
        logger.exception("Error researching trends: %s", e)
        return {"error": str(e), "trend_data": "No trend data available"}


def generate_tweet_node(state: AgentState) -> dict:
    """Generate strategic FDWA-branded tweet using Google AI.

    Args:
        state: Current agent state with trend_data.

    Returns:
        Dictionary with tweet_text or error.
    """
    logger.info("---GENERATING FDWA TWEET---")

    trend_data = state.get("trend_data", "")
    
    # Initialize the Google AI model
    llm = GoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.8,
        google_api_key=os.getenv("GOOGLE_AI_API_KEY")
    )

    # Enhanced FDWA master prompt
    prompt = f"""
You are the FDWA Autonomous Social Media Agent. Your voice is strategic, confident, and culturally aware. Write for entrepreneurs, creators, and founders building systems, not just hustling.

TRENDING DATA:
{trend_data[:2000]}

TASK:
From the trend data above, extract ONE insight that aligns with FDWA brand positioning: "We automate your business so your business can run itself."

Create ONE tweet under 275 characters (all characters count, including emojis and hashtags).

TWEET REQUIREMENTS:
- Tone: Futuristic, grounded, empowering (not hype, not corporate)
- Include 2 to 3 emojis max
- Include EXACTLY 5 hashtags: mix of trending + evergreen
- No bullet points, no lists, no quotes, no markdown
- CTA must be subtle and conversational (ex: "Your thoughts?" / "Let's build smarter." / "Tap in if you're ready.")

OUTPUT FORMAT:
Return ONLY the final tweet text. No explanations. No commentary. No JSON. No hashtags list outside the tweet.
"""

    try:
        # Invoke the model
        response = llm.invoke(prompt)
        generated_text = response.strip()

        # Remove problematic unicode characters
        generated_text = generated_text.encode("ascii", "ignore").decode("ascii")

        logger.info("Generated Tweet: %s", generated_text)
        logger.info("Character count: %d", len(generated_text))

        return {"tweet_text": generated_text}

    except Exception as e:
        logger.exception("Error generating tweet: %s", e)
        return {"error": str(e)}


def generate_image_node(state: AgentState) -> dict:
    """Generate and download an image using Pollinations API based on the tweet text.

    Args:
        state: Current agent state with tweet_text.

    Returns:
        Dictionary with image_url or error.
    """
    logger.info("---GENERATING IMAGE---")
    tweet_text = state.get("tweet_text", "")

    if not tweet_text:
        return {"error": "No tweet text for image generation"}

    # Use sub-agent to enhance prompt
    visual_prompt = _enhance_prompt_for_image(tweet_text)
    
    # Pollinations API configuration
    width = 1024
    height = 1024
    random_seed = random.randint(1, 100000)
    model = "flux"
    enhance = "true"
    nologo = "true"
    
    # URL encode the clean prompt
    encoded_prompt = visual_prompt.replace(" ", "%20")
    
    # Build Pollinations image URL
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={random_seed}&model={model}&enhance={enhance}&nologo={nologo}"

    logger.info("Image URL: %s", image_url)

    return {"image_url": image_url}


def comment_on_facebook_node(state: AgentState) -> dict:
    """Comment on the Facebook post with company URL.

    Args:
        state: Current agent state with facebook_post_id.

    Returns:
        Dictionary with comment_status.
    """
    logger.info("---COMMENTING ON FACEBOOK POST---")
    facebook_post_id = state.get("facebook_post_id")

    if not facebook_post_id:
        logger.warning("No Facebook post ID, skipping comment")
        return {"comment_status": "Skipped: No post ID"}

    # Wait 10 seconds for Facebook to process the post
    logger.info("Waiting 10 seconds for post to be processed...")
    time.sleep(10)
    logger.info("Proceeding with comment")

    comment_message = "Learn more at https://fdwa.site 🚀"

    try:
        comment_response = composio_client.tools.execute(
            "FACEBOOK_CREATE_COMMENT",
            {
                "message": comment_message,
                "object_id": facebook_post_id,
            },
            connected_account_id="ca_ztimDVH28syB",
        )

        comment_data = comment_response.get("data", {})
        comment_id = comment_data.get("id", "commented")
        logger.info("Facebook comment posted successfully!")
        logger.info("Comment ID: %s", comment_id)
        return {"comment_status": f"Commented: {comment_id}"}

    except Exception as e:
        logger.exception("Facebook comment failed: %s", e)
        return {"comment_status": f"Failed: {e!s}"}


def post_social_media_node(state: AgentState) -> dict:
    """Post the generated content to both Twitter and Facebook using Composio.

    Args:
        state: Current agent state with tweet_text and image_url.

    Returns:
        Dictionary with twitter_url and facebook_status.
    """
    logger.info("---POSTING TO SOCIAL MEDIA---")
    tweet_text = state.get("tweet_text")
    image_url = state.get("image_url")
    image_path = state.get("image_path")

    if not tweet_text:
        return {"error": "Tweet text is empty, skipping post."}

    if image_url:
        logger.info("Image URL: %s", image_url)
    else:
        logger.info("No image generated")

    if image_path:
        logger.info("Image Path: %s", image_path)
    else:
        logger.info("No image file")

    # Ensure tweet is within 280 character limit for Twitter
    twitter_text = tweet_text
    if len(twitter_text) > 280:
        twitter_text = twitter_text[:277] + "..."
        logger.info("Twitter text truncated to 280 characters")

    results = {}

    # Post to Twitter
    logger.info("Posting to Twitter: %s", twitter_text)
    try:
        twitter_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            {"text": twitter_text},
            connected_account_id="ca_tu9cBVOMM94b",
        )
        twitter_data = twitter_response.get("data", {})
        twitter_id = twitter_data.get("id", "unknown")
        twitter_url = (
            f"https://twitter.com/user/status/{twitter_id}"
            if twitter_id != "unknown"
            else "Twitter posted successfully"
        )
        results["twitter_url"] = twitter_url
        logger.info("Twitter posted successfully! URL: %s", twitter_url)
    except Exception as e:
        logger.exception("Twitter posting failed: %s", e)
        results["twitter_url"] = f"Twitter failed: {e!s}"
    
    # Post to Facebook
    logger.info("Posting to Facebook")
    logger.info("Message: %s", tweet_text)
    logger.info("Page ID: %s", os.getenv("FACEBOOK_PAGE_ID"))
    logger.info("Image File: %s", image_path if image_path else "None")
    logger.info("Published: True")
    try:
        facebook_params = {
            "page_id": os.getenv("FACEBOOK_PAGE_ID"),
            "message": tweet_text,
            "published": True,
        }

        # Add photo URL (Pollinations URL is publicly accessible)
        if image_url:
            facebook_params["url"] = image_url
            logger.info("Image URL attached: %s", image_url)
        else:
            logger.info("No image URL available")

        facebook_response = composio_client.tools.execute(
            "FACEBOOK_CREATE_PHOTO_POST",
            facebook_params,
            connected_account_id="ca_ztimDVH28syB",
        )

        facebook_data = facebook_response.get("data", {})
        facebook_post_id = facebook_data.get("id", "")
        results["facebook_status"] = f"Posted: {facebook_post_id}"
        results["facebook_post_id"] = facebook_post_id
        logger.info("Facebook posted successfully!")
        logger.info("Post ID: %s", facebook_post_id)
        logger.info("Response: %s", facebook_data)
    except Exception as e:
        logger.exception("Facebook posting failed: %s", e)
        results["facebook_status"] = f"Failed: {e!s}"
    
    return results


# Define the autonomous graph structure
workflow = StateGraph(AgentState)

# Add the nodes
workflow.add_node("research_trends", research_trends_node)
workflow.add_node("generate_content", generate_tweet_node)
workflow.add_node("generate_image", generate_image_node)
workflow.add_node("post_social_media", post_social_media_node)
workflow.add_node("comment_on_facebook", comment_on_facebook_node)

# Set the entrypoint
workflow.set_entry_point("research_trends")

# Add edges to define the autonomous flow
workflow.add_edge("research_trends", "generate_content")
workflow.add_edge("generate_content", "generate_image")
workflow.add_edge("generate_image", "post_social_media")
workflow.add_edge("post_social_media", "comment_on_facebook")
workflow.add_edge("comment_on_facebook", "__end__")

# Compile the graph
graph = workflow.compile()


# Autonomous execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting FDWA Autonomous Social Media AI Agent...")

    # No manual input needed - fully autonomous
    inputs = {}

    try:
        final_state = graph.invoke(inputs)

        logger.info("\nAUTONOMOUS EXECUTION COMPLETE")
        logger.info("Tweet: %s", final_state.get("tweet_text", "N/A"))
        logger.info("Image: %s", final_state.get("image_url", "N/A"))
        logger.info("Twitter: %s", final_state.get("twitter_url", "N/A"))
        logger.info("Facebook: %s", final_state.get("facebook_status", "N/A"))
        logger.info("Comment: %s", final_state.get("comment_status", "N/A"))

        if final_state.get("error"):
            logger.error("Error: %s", final_state.get("error"))

    except Exception:
        logger.exception("Agent execution failed")