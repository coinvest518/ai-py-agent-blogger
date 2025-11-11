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
from src.agent.linkedin_agent import convert_to_linkedin_post
from src.agent.instagram_agent import convert_to_instagram_caption
from src.agent.instagram_comment_agent import generate_instagram_reply

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
        linkedin_text: The LinkedIn post text.
        image_url: The URL of the generated image.
        image_path: The local path of the generated image.
        twitter_url: The URL of the created Twitter post.
        facebook_status: The status of the Facebook post.
        facebook_post_id: The ID of the Facebook post.
        linkedin_status: The status of the LinkedIn post.
        comment_status: The status of the Facebook comment.
        error: To capture any errors that might occur.
    """
    trend_data: str
    insight: str
    tweet_text: str
    linkedin_text: str
    instagram_caption: str
    image_url: str
    image_path: str
    twitter_url: str
    twitter_post_id: str
    twitter_reply_status: str
    facebook_status: str
    facebook_post_id: str
    linkedin_status: str
    instagram_status: str
    instagram_post_id: str
    instagram_comment_status: str
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

    # FWDA-specific search queries for SMB AI automation trends
    search_queries = [
        "AI automation for small business 2025",
        "AI workflows for service businesses",
        "AI business systems 2025",
        "AI agents replacing administrative work",
        "SMB productivity automation statistics",
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

    # FWDA Marketing Intelligence prompt
    prompt = f"""
You are the Marketing Intelligence & Content Strategy AI Agent for FWDA AI Automation Agency.

BRAND POSITIONING:
FWDA builds custom AI automation workflows, systems, and client pipelines that reduce workload and increase revenue capacity for small and medium-sized service businesses.

TARGET AUDIENCE:
Small/medium service businesses (coaches, agencies, consultants, trades, wellness, beauty, fitness, local businesses) struggling with manual workflows, inconsistent leads, operational overwhelm, repetitive tasks.

TRENDING DATA (last 90 days):
{trend_data[:2000]}

TASK:
Extract 2-3 concrete insights (adoption rates, cost savings, productivity improvements, SMB tech urgency) and create a social post.

TWITTER POST REQUIREMENTS (MAX 240 CHARACTERS including spaces, emojis, hashtags, links):
- Hook: One compelling sentence about SMB AI trend
- Problem + Solution: Brief statement of problem and how FWDA solves it
- Include EXACTLY 2 emojis (placed naturally in text)
- Include 3-5 hashtags at end
- Include ONE link: https://fwda.site
- Tone: Direct, confident, conversational
- Format: Short, punchy, Twitter-native style
- Count ALL characters including spaces

QUALITY RULES:
- No generic clichés
- Must be under 240 characters total
- Benefits must be clear
- Active voice

Return ONLY the Twitter post text. No explanations. No extra content.
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


def monitor_instagram_comments_node(state: AgentState) -> dict:
    """Monitor Instagram post for comments and reply.

    Args:
        state: Current agent state with instagram_post_id.

    Returns:
        Dictionary with instagram_comment_status.
    """
    logger.info("---MONITORING INSTAGRAM COMMENTS---")
    instagram_post_id = state.get("instagram_post_id")

    if not instagram_post_id:
        logger.warning("No Instagram post ID, skipping comment monitoring")
        return {"instagram_comment_status": "Skipped: No post ID"}

    # Wait 30 seconds for comments to come in
    logger.info("Waiting 30 seconds for comments...")
    time.sleep(30)

    try:
        # Get comments on the post
        comments_response = composio_client.tools.execute(
            "INSTAGRAM_GET_POST_COMMENTS",
            {"ig_post_id": instagram_post_id, "limit": 5},
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        )

        logger.info("Instagram comments response: %s", comments_response)
        
        if not comments_response.get("successful", False):
            return {"instagram_comment_status": "No comments yet"}

        comments_data = comments_response.get("data", {}).get("data", [])
        
        if not comments_data:
            logger.info("No comments found")
            return {"instagram_comment_status": "No comments yet"}

        # Reply to first comment
        first_comment = comments_data[0]
        comment_id = first_comment.get("id", "")
        comment_text = first_comment.get("text", "")
        commenter_username = first_comment.get("username", "user")

        logger.info("Replying to comment from @%s: %s", commenter_username, comment_text)

        # Generate reply
        reply_text = generate_instagram_reply(comment_text, commenter_username)

        # Post reply
        reply_response = composio_client.tools.execute(
            "INSTAGRAM_REPLY_TO_COMMENT",
            {"ig_comment_id": comment_id, "message": reply_text},
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        )

        if reply_response.get("successful", False):
            logger.info("Instagram reply posted successfully!")
            return {"instagram_comment_status": f"Replied to @{commenter_username}"}
        else:
            error_msg = reply_response.get("error", "Reply failed")
            logger.error("Instagram reply failed: %s", error_msg)
            return {"instagram_comment_status": f"Failed: {error_msg}"}

    except Exception as e:
        logger.exception("Instagram comment monitoring failed: %s", e)
        return {"instagram_comment_status": f"Failed: {e!s}"}


def reply_to_twitter_node(state: AgentState) -> dict:
    """Reply to own Twitter post with FWDA link.

    Args:
        state: Current agent state with twitter_post_id.

    Returns:
        Dictionary with twitter_reply_status.
    """
    logger.info("---REPLYING TO TWITTER POST---")
    twitter_post_id = state.get("twitter_post_id")

    if not twitter_post_id:
        logger.warning("No Twitter post ID, skipping reply")
        return {"twitter_reply_status": "Skipped: No post ID"}

    # Wait 60 seconds before replying
    logger.info("Waiting 60 seconds before replying...")
    time.sleep(60)
    logger.info("Proceeding with reply")

    reply_message = "Learn more about AI automation for your business: https://fwda.site 🚀"

    try:
        reply_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            {
                "text": reply_message,
                "reply_in_reply_to_tweet_id": twitter_post_id
            },
            connected_account_id="ca_tu9cBVOMM94b",
        )

        reply_data = reply_response.get("data", {})
        reply_id = reply_data.get("id", "replied")
        logger.info("Twitter reply posted successfully!")
        logger.info("Reply ID: %s", reply_id)
        return {"twitter_reply_status": f"Replied: {reply_id}"}

    except Exception as e:
        logger.exception("Twitter reply failed: %s", e)
        return {"twitter_reply_status": f"Failed: {e!s}"}


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


def post_instagram_node(state: AgentState) -> dict:
    """Post to Instagram with image and caption.

    Args:
        state: Current agent state with instagram_caption and image_url.

    Returns:
        Dictionary with instagram_status.
    """
    logger.info("---POSTING TO INSTAGRAM---")
    tweet_text = state.get("tweet_text", "")
    image_url = state.get("image_url")

    if not tweet_text or not image_url:
        return {"instagram_status": "Skipped: No content or image"}

    # Convert tweet to Instagram caption
    instagram_caption = convert_to_instagram_caption(tweet_text)
    logger.info("Instagram caption: %s", instagram_caption[:100])

    try:
        # Get Instagram user ID from environment
        ig_user_id = os.getenv("INSTAGRAM_USER_ID")
        
        if not ig_user_id:
            logger.error("Instagram user ID not configured")
            return {"instagram_status": "Failed: No user ID", "instagram_caption": instagram_caption}

        # Create media container
        container_params = {
            "ig_user_id": ig_user_id,
            "image_url": image_url,
            "caption": instagram_caption,
            "content_type": "photo"
        }

        container_response = composio_client.tools.execute(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            container_params,
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        )

        logger.info("Instagram container response: %s", container_response)
        
        if container_response.get("successful", False):
            container_id = container_response.get("data", {}).get("id", "")
            
            # Wait for Instagram to process the media (required by Instagram API)
            logger.info("Waiting 10 seconds for Instagram to process media...")
            time.sleep(10)
            
            # Publish the container
            publish_response = composio_client.tools.execute(
                "INSTAGRAM_CREATE_POST",
                {"ig_user_id": ig_user_id, "creation_id": container_id},
                connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
            )
            
            if publish_response.get("successful", False):
                post_id = publish_response.get("data", {}).get("id", "")
                logger.info("Instagram posted successfully! Post ID: %s", post_id)
                return {"instagram_status": "Posted", "instagram_caption": instagram_caption, "instagram_post_id": post_id}
            else:
                error_msg = publish_response.get("error", "Publish failed")
                logger.error("Instagram publish failed: %s", error_msg)
                return {"instagram_status": f"Failed: {error_msg}", "instagram_caption": instagram_caption}
        else:
            error_msg = container_response.get("error", "Container creation failed")
            logger.error("Instagram container failed: %s", error_msg)
            return {"instagram_status": f"Failed: {error_msg}", "instagram_caption": instagram_caption}

    except Exception as e:
        logger.exception("Instagram posting failed: %s", e)
        return {"instagram_status": f"Failed: {e!s}", "instagram_caption": instagram_caption}


def post_linkedin_node(state: AgentState) -> dict:
    """Post to LinkedIn using converted text.

    Args:
        state: Current agent state with linkedin_text and image_url.

    Returns:
        Dictionary with linkedin_status.
    """
    logger.info("---POSTING TO LINKEDIN---")
    tweet_text = state.get("tweet_text", "")
    image_url = state.get("image_url")

    if not tweet_text:
        return {"linkedin_status": "Skipped: No content"}

    # Convert tweet to LinkedIn post
    linkedin_text = convert_to_linkedin_post(tweet_text)
    logger.info("LinkedIn post: %s", linkedin_text[:100])

    try:
        linkedin_account_id = os.getenv("LINKEDIN_ACCOUNT_ID")
        
        if not linkedin_account_id:
            logger.error("LINKEDIN_ACCOUNT_ID not set in environment")
            return {"linkedin_status": "Failed: No account ID", "linkedin_text": linkedin_text}
        
        # First, get the user info to retrieve the correct author URN
        logger.info("Fetching LinkedIn user info to get author URN...")
        user_info_response = composio_client.tools.execute(
            "LINKEDIN_GET_MY_INFO",
            {},
            connected_account_id=linkedin_account_id,
        )
        
        logger.info("LinkedIn user info response: %s", user_info_response)
        
        if not user_info_response.get("successful", False):
            error_msg = user_info_response.get("error", "Failed to get user info")
            logger.error("Failed to get LinkedIn user info: %s", error_msg)
            return {"linkedin_status": f"Failed: {error_msg}", "linkedin_text": linkedin_text}
        
        # Extract author_id (URN) from nested response_dict
        user_data = user_info_response.get("data", {})
        response_dict = user_data.get("response_dict", {})
        author_urn = response_dict.get("author_id", "")
        
        if not author_urn:
            logger.error("No author_id found in user info response")
            return {"linkedin_status": "Failed: No author URN in response", "linkedin_text": linkedin_text}
        
        logger.info("Using author URN from API: %s", author_urn)

        linkedin_params = {
            "author": author_urn,
            "commentary": linkedin_text,
            "visibility": "PUBLIC"
        }

        linkedin_response = composio_client.tools.execute(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            linkedin_params,
            connected_account_id=linkedin_account_id,
        )

        logger.info("LinkedIn response: %s", linkedin_response)
        
        if linkedin_response.get("successful", False):
            logger.info("LinkedIn posted successfully!")
            return {"linkedin_status": "Posted", "linkedin_text": linkedin_text}
        else:
            error_msg = linkedin_response.get("error", "Unknown error")
            logger.error("LinkedIn post failed: %s", error_msg)
            return {"linkedin_status": f"Failed: {error_msg}", "linkedin_text": linkedin_text}

    except Exception as e:
        logger.exception("LinkedIn posting failed: %s", e)
        return {"linkedin_status": f"Failed: {e!s}", "linkedin_text": linkedin_text}


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
        results["twitter_post_id"] = twitter_id
        logger.info("Twitter posted successfully! URL: %s", twitter_url)
        logger.info("Twitter Post ID: %s", twitter_id)
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

        # Composio response structure: {"data": {...}, "successful": bool, "error": null}
        logger.info("Facebook response: %s", facebook_response)
        
        # Check if post was successful
        if not facebook_response.get("successful", False):
            error_msg = facebook_response.get("error", "Unknown error")
            logger.error("Facebook post failed: %s", error_msg)
            results["facebook_status"] = f"Failed: {error_msg}"
            results["facebook_post_id"] = ""
            return results
        
        # Extract data from Composio response
        # Structure: {"data": {"response_data": {"id": "...", "post_id": "..."}}}
        facebook_data = facebook_response.get("data", {})
        response_data = facebook_data.get("response_data", {})
        
        # Use post_id (full format: PAGE_ID_POST_ID) for commenting
        facebook_post_id = response_data.get("post_id", "")
        
        logger.info("Facebook posted successfully!")
        logger.info("Post ID: %s", facebook_post_id)
        
        results["facebook_status"] = f"Posted: {facebook_post_id}"
        results["facebook_post_id"] = facebook_post_id
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
workflow.add_node("post_linkedin", post_linkedin_node)
workflow.add_node("post_instagram", post_instagram_node)
workflow.add_node("monitor_instagram_comments", monitor_instagram_comments_node)
workflow.add_node("reply_to_twitter", reply_to_twitter_node)
workflow.add_node("comment_on_facebook", comment_on_facebook_node)

# Set the entrypoint
workflow.set_entry_point("research_trends")

# Add edges to define the autonomous flow
workflow.add_edge("research_trends", "generate_content")
workflow.add_edge("generate_content", "generate_image")
workflow.add_edge("generate_image", "post_social_media")
workflow.add_edge("post_social_media", "post_linkedin")
workflow.add_edge("post_linkedin", "post_instagram")
workflow.add_edge("post_instagram", "monitor_instagram_comments")
workflow.add_edge("monitor_instagram_comments", "reply_to_twitter")
workflow.add_edge("reply_to_twitter", "comment_on_facebook")
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
        logger.info("LinkedIn: %s", final_state.get("linkedin_status", "N/A"))
        logger.info("Instagram: %s", final_state.get("instagram_status", "N/A"))
        logger.info("Instagram Comments: %s", final_state.get("instagram_comment_status", "N/A"))
        logger.info("Twitter Reply: %s", final_state.get("twitter_reply_status", "N/A"))
        logger.info("Facebook Comment: %s", final_state.get("comment_status", "N/A"))

        if final_state.get("error"):
            logger.error("Error: %s", final_state.get("error"))

    except Exception:
        logger.exception("Agent execution failed")