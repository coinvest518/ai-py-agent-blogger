"""FDWA Autonomous Twitter AI Agent.

This graph defines a three-step autonomous process:
1. Research trending topics using SERPAPI (primary) with Tavily fallback
2. Generate strategic FDWA-branded tweet using Google AI
3. Post the tweet to Twitter using Composio
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
import requests
from pathlib import Path
from typing import TypedDict

from composio import Composio
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAI
from langsmith import traceable
from langsmith.integrations.otel import configure
from langgraph.graph import StateGraph
from src.agent.linkedin_agent import convert_to_linkedin_post
from src.agent.instagram_agent import convert_to_instagram_caption
from src.agent.instagram_comment_agent import generate_instagram_reply
from src.agent.blog_email_agent import generate_and_send_blog

# Load environment variables from .env file
load_dotenv()

# Configure LangSmith OpenTelemetry integration for Google models
configure(project_name=os.getenv("LANGSMITH_PROJECT", "fdwa-multi-agent"))

# Initialize Composio client with env entity_id
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id=os.getenv("TWITTER_ENTITY_ID")
)

# Configure logging
logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    """Represents the state of our autonomous agent.

    Attributes:
        trend_data: Raw trend data from SERPAPI or Tavily search.
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
    blog_status: str
    blog_title: str
    error: str


def _download_image_from_url(image_url: str) -> str:
    """Download image from URL and save locally.
    
    Args:
        image_url: URL of the image to download.
        
    Returns:
        Local file path of downloaded image.
    """
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Create temp directory if it doesn't exist
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        # Extract filename from URL or generate one
        filename = image_url.split("/")[-1] or "image.jpg"
        if not filename.endswith((".jpg", ".jpeg", ".png")):
            filename += ".jpg"
        
        local_path = temp_dir / filename
        local_path.write_bytes(response.content)
        
        logger.info("Downloaded image to: %s", local_path)
        return str(local_path)
    except Exception as e:
        logger.exception("Failed to download image: %s", e)
        return None


@traceable(name="enhance_image_prompt")
def _enhance_prompt_for_image(text: str) -> str:
    """Convert social media text into a clean visual prompt for image generation.

    Args:
        text: Social media post text with hashtags and formatting.

    Returns:
        Clean, descriptive image prompt optimized for Google Gemini AI image generation.
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
- Futuristic neon cyberpunk style
- Credit report visuals or clean business graphics
- Urban + modern energy
- African-American models when applicable
- Digital holograms and AI automation scenes
- Minimalist typography with Gen Z design flair
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
    """Research trending topics using SERPAPI with Tavily fallback.

    Args:
        state: Current agent state.

    Returns:
        Dictionary with trend_data or error.
    """
    logger.info("---RESEARCHING TRENDS---")

    # Diverse search queries for different business topics
    search_queries = [
        "credit repair tips 2025",
        "AI automation for credit repair",
        "digital products for financial freedom",
        "AI dispute letter generators",
        "passive income with ebooks",
        "credit score improvement hacks",
        "AI tools for business automation",
        "how to sell digital products online",
        "financial empowerment strategies",
        "credit repair laws and updates",
        "AI credit report analyzers",
        "building wealth with digital tools",
        "credit denial solutions",
        "automate business workflows with AI",
        "create and sell step-by-step guides",
        "financial education for entrepreneurs",
        "credit repair digital products",
        "AI for passive income streams",
        "modern wealth building techniques",
        "credit repair automation tools",
    ]

    query = random.choice(search_queries)
    logger.info("Researching: %s", query)

    trend_data = ""

    try:
        # Primary: Try SERPAPI search first
        logger.info("Fetching search results with SERPAPI...")
        try:
            search_response = composio_client.tools.execute(
                "SERPAPI_SEARCH",
                {"query": query},
                connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
            )
            trend_data = f"SERPAPI_SEARCH: {search_response.get('data', {})!s}"
            logger.info("SERPAPI search successful: %d characters", len(trend_data))
            return {"trend_data": trend_data}
            
        except Exception as serpapi_error:
            logger.warning("SERPAPI search failed: %s", serpapi_error)
            
            # Fallback: Try Tavily search
            logger.info("Falling back to Tavily search...")
            search_response = composio_client.tools.execute(
                "TAVILY_SEARCH",
                {
                    "query": query,
                    "max_results": 10,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": True,
                    "exclude_domains": [
                        "pinterest.com",
                        "facebook.com", 
                        "instagram.com",
                        "twitter.com",
                        "tiktok.com"
                    ]
                },
                connected_account_id=os.getenv("TAVILY_ACCOUNT_ID")
            )
            trend_data = f"TAVILY_SEARCH: {search_response.get('data', {})!s}"
            logger.info("Tavily fallback successful: %d characters", len(trend_data))
            return {"trend_data": trend_data}

    except Exception as e:
        logger.exception("Both search methods failed: %s", e)
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

    # Content generation prompt
    prompt = f"""
Create a Twitter post (max 240 characters) based on this trending data:

{trend_data[:1000]}

Topic: Credit repair, AI automation, digital products, or financial empowerment

Format:
- Hook (1 line problem/question)
- Quick value/tip
- CTA with link: https://fdwa.site
- 2 emojis
- 3-5 hashtags

Must be under 240 characters total. No markdown. Plain text only.
"""

    try:
        response = llm.invoke(prompt)
        generated_text = response.strip()

        # Remove markdown and problematic characters
        generated_text = re.sub(r'\*\*', '', generated_text)
        generated_text = re.sub(r'\*', '', generated_text)
        generated_text = re.sub(r'#{1,6}\s', '', generated_text)
        generated_text = generated_text.encode("ascii", "ignore").decode("ascii")
        
        # Ensure under 280 characters
        if len(generated_text) > 280:
            generated_text = generated_text[:277] + "..."

        logger.info("Generated Tweet: %s", generated_text)
        logger.info("Character count: %d", len(generated_text))

        return {"tweet_text": generated_text}

    except Exception as e:
        logger.exception("Error generating tweet: %s", e)
        return {"error": str(e)}


def generate_image_node(state: AgentState) -> dict:
    """Generate an image using Google Gemini via Composio based on the tweet text.

    Args:
        state: Current agent state with tweet_text.

    Returns:
        Dictionary with image_url or error.
    """
    logger.info("---GENERATING IMAGE WITH GEMINI---")
    tweet_text = state.get("tweet_text", "")

    if not tweet_text:
        return {"error": "No tweet text for image generation"}

    # Use sub-agent to enhance prompt
    visual_prompt = _enhance_prompt_for_image(tweet_text)
    
    logger.info("Enhanced visual prompt: %s", visual_prompt)
    
    try:
        # Use Gemini image generation via Composio (toolkit_version is invalid parameter)
        image_response = composio_client.tools.execute(
            "GEMINI_GENERATE_IMAGE",
            {
                "prompt": visual_prompt,
                "model": "gemini-2.5-flash-image-preview",
                "temperature": 0.7,
                "system_instruction": "Generate a professional, modern business image that aligns with AI automation and small business themes. Style should be clean, futuristic, and engaging for social media."
            }
        )
        
        logger.info("Gemini image response: %s", image_response)
        logger.info("Gemini response data structure: %s", image_response.get("data", {}))
        
        if image_response.get("successful", False):
            # Extract S3 URL from Gemini MCP content array (using working test logic)
            image_data = image_response.get("data", {})
            content_array = image_data.get("content", [])
            
            image_url = None
            
            # Look for image in content array (matching test file logic)
            for content_block in content_array:
                if isinstance(content_block, dict):
                    if content_block.get("type") == "image":
                        if "source" in content_block and "media_type" in content_block["source"]:
                            # Direct S3 URL in source
                            source_data = content_block["source"].get("data", "")
                            if source_data.startswith("https://"):
                                image_url = source_data
                                break
                    elif content_block.get("type") == "text":
                        # Check if text content contains S3 URL
                        text_content = content_block.get("text", "")
                        if text_content.startswith("https://") and "r2.dev" in text_content:
                            image_url = text_content
                            break
                    elif "image_url" in content_block:
                        # Alternative format
                        image_url = content_block["image_url"]
                        break
            
            # Fallback: try direct extraction from data
            if not image_url:
                image_url = image_data.get("image_url") or image_data.get("url") or image_data.get("s3_url")
            
            if image_url:
                logger.info("Generated image URL: %s", image_url)
                return {"image_url": image_url}
            else:
                logger.error("No image URL found in Gemini response. Data structure: %s", image_data)
                return {"error": "No image URL returned from Gemini"}
        else:
            error_msg = image_response.get("error", "Unknown Gemini error")
            logger.error("Gemini image generation failed: %s", error_msg)
            return {"error": f"Gemini generation failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Error generating image with Gemini: %s", e)
        return {"error": f"Image generation error: {e!s}"}


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

    # Wait 5 seconds before replying
    logger.info("Waiting 5 seconds before replying...")
    time.sleep(5)
    logger.info("Proceeding with reply")

    reply_message = "Learn more about AI Consulting and Development for your business: https://fdwa.site 🚀"

    try:
        reply_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            {
                "text": reply_message,
                "reply_in_reply_to_tweet_id": twitter_post_id
            },
            connected_account_id=os.getenv("TWITTER_ACCOUNT_ID"),
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


def generate_blog_email_node(state: AgentState) -> dict:
    """Generate blog content and send via email.

    Args:
        state: Current agent state with trend_data.

    Returns:
        Dictionary with blog_status and blog_title.
    """
    logger.info("---GENERATING AND SENDING BLOG EMAIL---")
    trend_data = state.get("trend_data", "")
    
    try:
        blog_result = generate_and_send_blog(trend_data)
        
        if "error" in blog_result:
            logger.error("Blog generation failed: %s", blog_result["error"])
            return {"blog_status": f"Failed: {blog_result['error']}", "blog_title": ""}
        
        logger.info("Blog email process completed successfully!")
        logger.info("Blog title: %s", blog_result["blog_title"])
        logger.info("Email status: %s", blog_result["email_status"])
        
        return {
            "blog_status": blog_result["email_status"],
            "blog_title": blog_result["blog_title"]
        }
        
    except Exception as e:
        logger.exception("Blog email node failed: %s", e)
        return {"blog_status": f"Failed: {str(e)}", "blog_title": ""}


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
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID")
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
                connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID")
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
        # Hardcoded LinkedIn credentials (same pattern as Twitter/Facebook)
        linkedin_account_id = "ca_uL1KFpD-8ZfO"
        author_urn = "urn:li:person:980H7U657m"
        
        logger.info("Using LinkedIn account: %s", linkedin_account_id)
        logger.info("Using author URN: %s", author_urn)

        linkedin_params = {
            "author": author_urn,
            "commentary": linkedin_text,
            "visibility": "PUBLIC"
        }
        
        # Note: LinkedIn text posts only - image support requires different API endpoints

        linkedin_response = composio_client.tools.execute(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            linkedin_params,
            connected_account_id=os.getenv("LINKEDIN_ACCOUNT_ID")
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
    twitter_text = tweet_text
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
    if not twitter_text:
        twitter_text = tweet_text or ""
    if len(twitter_text) > 280:
        twitter_text = twitter_text[:277] + "..."
        logger.info("Twitter text truncated to 280 characters")

    results = {}

    # Post to Twitter with image support
    logger.info("Posting to Twitter: %s", twitter_text)
    try:
        twitter_params = {"text": twitter_text}
        
        # Upload media if image is available
        if image_url:
            logger.info("Uploading image to Twitter: %s", image_url)
            try:
                # Download image locally first
                local_image_path = _download_image_from_url(image_url)
                
                if local_image_path:
                    # Make sure path is absolute
                    import os
                    local_image_path = os.path.abspath(local_image_path)
                    logger.warning("Local image path: %s", local_image_path)
                    logger.warning("File exists: %s", os.path.exists(local_image_path))
                    
                    media_upload_response = composio_client.tools.execute(
                        "TWITTER_UPLOAD_MEDIA",
                        {
                            "media": local_image_path,
                            "media_category": "tweet_image"
                        },
                        connected_account_id=os.getenv("TWITTER_ACCOUNT_ID")
                    )
                    
                    logger.warning("Twitter media upload response: %s", media_upload_response)
                    
                    if media_upload_response.get("successful", False):
                        logger.warning("Full media upload response: %s", media_upload_response)
                        # Always extract the media ID from the correct nested field
                        nested_data = media_upload_response.get("data", {})
                        if isinstance(nested_data, dict):
                            media_data = nested_data.get("data", {})
                        else:
                            media_data = {}
                        logger.warning("media_data: %s", media_data)
                        logger.warning("media_data keys: %s", list(media_data.keys()) if isinstance(media_data, dict) else "not dict")
                        media_id = media_data.get("id")
                        logger.warning("Extracted media_id from nested response: %s", media_id)
                        if media_id and str(media_id) not in ["{}", "None", ""]:
                            twitter_params["media_media_ids"] = [str(media_id)]
                            logger.warning("Twitter media uploaded successfully, ID: %s", media_id)
                            logger.warning("Twitter params now include media: %s", twitter_params)
                        else:
                            logger.warning("No media ID returned from Twitter upload. media_id: %s, str(media_id): %s", media_id, str(media_id))
                    else:
                        logger.error("Twitter media upload failed: %s", media_upload_response.get("error"))
                else:
                    logger.error("Failed to download image from URL: %s", image_url)
                    
            except Exception as media_e:
                logger.exception("Twitter media upload error: %s", media_e)
                # Continue with text-only post if media upload fails
        
        # Create the post (with or without media)
        twitter_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            twitter_params,
            connected_account_id=os.getenv("TWITTER_ACCOUNT_ID")
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

        # Add photo by downloading from URL first
        if image_url and image_url.strip() and image_url.startswith("https://"):
            local_image_path = _download_image_from_url(image_url)
            if local_image_path:
                facebook_params["photo"] = local_image_path
                logger.info("Facebook photo attached using local path: %s", local_image_path)
                facebook_tool = "FACEBOOK_CREATE_PHOTO_POST"
            else:
                logger.error("Failed to download image from URL: %s", image_url)
                facebook_tool = "FACEBOOK_CREATE_POST"
        else:
            logger.info("No valid image URL available, posting text-only to Facebook")
            facebook_tool = "FACEBOOK_CREATE_POST"

        facebook_response = composio_client.tools.execute(
            facebook_tool,
            facebook_params,
            connected_account_id="ca_ztimDVH28syB"
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
workflow.add_node("generate_blog_email", generate_blog_email_node)

# Set the entrypoint
workflow.set_entry_point("research_trends")

# Add edges to define the autonomous flow
workflow.add_edge("research_trends", "generate_content")
workflow.add_edge("generate_content", "generate_image")
workflow.add_edge("generate_image", "post_social_media")
workflow.add_edge("post_social_media", "post_instagram")
# workflow.add_edge("post_linkedin", "post_instagram")  # LinkedIn bypassed
workflow.add_edge("post_instagram", "monitor_instagram_comments")
workflow.add_edge("monitor_instagram_comments", "reply_to_twitter")
workflow.add_edge("reply_to_twitter", "comment_on_facebook")
workflow.add_edge("comment_on_facebook", "generate_blog_email")
workflow.add_edge("generate_blog_email", "__end__")

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
        logger.info("Blog Email: %s", final_state.get("blog_status", "N/A"))
        logger.info("Blog Title: %s", final_state.get("blog_title", "N/A"))

        if final_state.get("error"):
            logger.error("Error: %s", final_state.get("error"))

    except Exception:
        logger.exception("Agent execution failed")