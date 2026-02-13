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
from langsmith import traceable
from langsmith.integrations.otel import configure
from langgraph.graph import StateGraph
from src.agent.linkedin_agent import convert_to_linkedin_post
from src.agent.instagram_agent import convert_to_instagram_caption
from src.agent.instagram_comment_agent import generate_instagram_reply
from src.agent.blog_email_agent import generate_and_send_blog
from src.agent import telegram_agent

# Load environment variables from .env file
load_dotenv()

# Configure LangSmith OpenTelemetry integration
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
    telegram_message: str
    telegram_status: str
    error: str


def _download_image_from_url(image_url: str) -> str:
    """Download image from URL and save locally.
    
    Args:
        image_url: URL of the image to download (https://) or local file path (file://).
        
    Returns:
        Local file path of downloaded image.
    """
    try:
        # Handle local file:// URIs (from Hugging Face local generation)
        if image_url.startswith("file:///"):
            local_path = image_url.replace("file:///", "").replace("/", chr(92))
            if os.path.exists(local_path):
                logger.info("Using local file: %s", local_path)
                return local_path
            else:
                logger.error("Local file not found: %s", local_path)
                return None
        
        # Download from remote URL
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
        Clean, descriptive image prompt optimized for Hugging Face Stable Diffusion.
    """
    logger.info("Enhancing image prompt...")

    # Template-based prompt enhancement (no AI needed)
    # Clean up text: remove hashtags, @ mentions, URLs, special chars
    clean_text = re.sub(r"#\w+", "", text)  # Remove hashtags
    clean_text = re.sub(r"@\w+", "", clean_text)  # Remove mentions
    clean_text = re.sub(r"https?://\S+", "", clean_text)  # Remove URLs
    clean_text = re.sub(r"[*#@\[\]{}()\'\"\\]", "", clean_text)  # Remove special chars
    clean_text = re.sub(r"\s+", " ", clean_text).strip()  # Normalize whitespace
    
    # Truncate to reasonable length (150 chars)
    clean_text = clean_text[:150]
    
    # Create structured prompt for Stable Diffusion
    visual_prompt = (
        f"Professional modern business image: {clean_text}. "
        "Futuristic neon cyberpunk style, clean business graphics, urban modern energy, "
        "digital holograms, AI automation scenes, minimalist Gen Z design, high quality, 4k"
    )
    
    logger.info("Generated visual prompt: %s", visual_prompt[:100])
    return visual_prompt


def research_trends_node(state: AgentState) -> dict:
    """Research trending topics using SERPAPI with Tavily fallback.

    Args:
        state: Current agent state.

    Returns:
        Dictionary with trend_data or error.
    """
    import json
    from datetime import datetime
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
    today = datetime.now().strftime("%Y-%m-%d")
    cache_file = "trend_cache.json"

    try:
        # Primary: Try SERPAPI search first
        logger.info("Fetching search results with SERPAPI...")
        try:
            search_response = composio_client.tools.execute(
                "SERPAPI_SEARCH",
                {"query": query},
                connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
            )
            # Remove error text if present
            data = search_response.get('data', {})
            if isinstance(data, dict) and any(
                k in str(data).lower() for k in ["account out of searches", "error", "limit"]):
                raise Exception("SERPAPI out of searches or error")
            trend_data = str(data)
            logger.info("SERPAPI search successful: %d characters", len(trend_data))
            return {"trend_data": trend_data}
        except Exception as serpapi_error:
            logger.warning("SERPAPI search failed: %s", serpapi_error)
            # Fallback: Try Tavily search, but only once per day
            logger.info("Falling back to Tavily search...")
            # Check cache
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if cache.get("date") == today and cache.get("trend_data"):
                    logger.info("Using cached Tavily trend data for today.")
                    return {"trend_data": cache["trend_data"]}
            # Not cached, do Tavily search
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
            trend_data = str(search_response.get('data', {}))
            # Save to cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"date": today, "trend_data": trend_data}, f)
            logger.info("Tavily fallback successful: %d characters", len(trend_data))
            return {"trend_data": trend_data}
    except Exception as e:
        logger.exception("Both search methods failed: %s", e)
        return {"error": str(e), "trend_data": "No trend data available"}


def generate_tweet_node(state: AgentState) -> dict:
    """Generate strategic FDWA-branded tweet using template-based formatting (no AI needed).

    Args:
        state: Current agent state with trend_data.

    Returns:
        Dictionary with tweet_text or error.
    """
    logger.info("---GENERATING FDWA TWEET---")

    trend_data = state.get("trend_data", "")
    # Remove any error or search system text from trend_data
    for bad in ["SERPAPI_SEARCH:", "TAVILY_SEARCH:", "Account out of searches", "error", "limit"]:
        if bad.lower() in trend_data.lower():
            trend_data = ""
            break

    # Template-based tweet generation (fast, no API calls)
    if trend_data:
        # Extract key topic from trend data
        summary = trend_data.strip()[:150]
        # Clean up for tweet
        summary = summary.split('\n')[0]  # First line only
        
        # Create branded tweet
        tweet = (
            f"🚀 {summary}\n\n"
            f"Get AI automation tools at https://fdwa.site ✨\n\n"
            f"#YBOT #AIAutomation #CreditRepair #FinancialFreedom"
        )
    else:
        # Fallback when no trend data
        tweet = (
            "💡 Transform your business with AI automation and smart credit strategies! "
            "Start building your financial future today. https://fdwa.site #YBOT #AIAgent"
        )
    
    # Ensure under 280 characters
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."

    logger.info("Generated Tweet: %s", tweet)
    logger.info("Character count: %d", len(tweet))

    return {"tweet_text": tweet}


def generate_image_node(state: AgentState) -> dict:
    """Generate an image using Hugging Face Inference API (FREE alternative to Google Gemini).

    Args:
        state: Current agent state with tweet_text.

    Returns:
        Dictionary with image_path (local file) and image_url (HTTP) or error.
    """
    logger.info("---GENERATING IMAGE WITH HUGGING FACE---")
    tweet_text = state.get("tweet_text", "")

    if not tweet_text:
        return {"error": "No tweet text for image generation"}

    # Use sub-agent to enhance prompt
    visual_prompt = _enhance_prompt_for_image(tweet_text)
    
    logger.info("Enhanced visual prompt: %s", visual_prompt)
    
    try:
        # Import Hugging Face image generator
        from src.agent.hf_image_gen import generate_image_hf, save_image_locally, upload_to_imgbb
        
        # Generate image with Hugging Face (FREE)
        result = generate_image_hf(
            prompt=visual_prompt,
            model="flux-schnell",  # FLUX.1-schnell - fast and high quality
            width=512,
            height=512,
        )
        
        if result.get("success"):
            # Save image locally
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hf_generated_{timestamp}.png"
            
            image_path = save_image_locally(result["image_bytes"], filename)
            logger.info("Generated image saved to: %s", image_path)
            
            # Upload to imgbb for public HTTP URL (needed for Instagram/Blog/Email)
            logger.info("Uploading to imgbb for public URL...")
            upload_result = upload_to_imgbb(result["image_bytes"])
            
            if upload_result.get("success"):
                http_url = upload_result["url"]
                logger.info("Image uploaded to imgbb: %s", http_url)
                
                return {
                    "image_path": image_path,
                    "image_url": http_url  # HTTP URL works everywhere
                }
            else:
                logger.warning("Upload to imgbb failed: %s", upload_result.get("error"))
                logger.info("Falling back to local file for Twitter/Facebook")
                
                # Return local file path - still works for Twitter/Facebook
                return {
                    "image_path": image_path,
                    "image_url": f"file:///{image_path.replace(chr(92), '/')}"  # Local fallback
                }
        else:
            error_msg = result.get("error", "Unknown HF error")
            logger.error("Hugging Face image generation failed: %s", error_msg)
            return {"error": f"HF generation failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Error generating image with Hugging Face: %s", e)
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
    """Generate blog content and send via email with image URL in body.

    Args:
        state: Current agent state with trend_data and image_url.

    Returns:
        Dictionary with blog_status and blog_title.
    """
    logger.info("---GENERATING AND SENDING BLOG EMAIL---")
    trend_data = state.get("trend_data", "")
    
    # Get the generated image URL from state
    image_url = state.get("image_url")
    
    if image_url:
        logger.info("Blog email will include image URL: %s", image_url[:60] if image_url else "None")
        # Set environment variable so blog_email_agent can access it
        os.environ["BLOG_IMAGE_URL"] = image_url
    else:
        logger.warning("No image URL available for blog email")
    
    try:
        blog_result = generate_and_send_blog(trend_data, image_url=image_url)
        
        if "error" in blog_result:
            logger.error("Blog generation failed: %s", blog_result["error"])
            return {"blog_status": f"Failed: {blog_result['error']}", "blog_title": ""}
        
        logger.info("Blog email process completed successfully!")
        logger.info("Blog title: %s", blog_result["blog_title"])
        logger.info("Email status: %s", blog_result["email_status"])
        logger.info("Image included: %s", blog_result.get("has_image", False))
        
        return {
            "blog_status": blog_result["email_status"],
            "blog_title": blog_result["blog_title"]
        }
        
    except Exception as e:
        logger.exception("Blog email node failed: %s", e)
        return {"blog_status": f"Failed: {str(e)}", "blog_title": ""}


def convert_to_telegram_crypto_post(trend_data: str, tweet_text: str) -> str:
    """Parse trend data and convert to Telegram crypto market update.
    
    This sub-agent extracts crypto/token data from the research and structures
    it into a Telegram-ready format with trends, top tokens, and market data.
    No additional SERP/Tavily calls - reuses existing research.
    No AI needed - uses template-based parsing.
    
    Args:
        trend_data: Raw research data from SERPAPI/Tavily
        tweet_text: Generated tweet for context
        
    Returns:
        Formatted Telegram message with crypto data
    """
    logger.info("---CONVERTING TO TELEGRAM CRYPTO POST---")
    
    # Template-based crypto post (no AI needed)
    # Extract potential crypto tokens from trend data
    crypto_keywords = ["BTC", "ETH", "SOL", "MATIC", "AVAX", "DOT", "LINK", "UNI", 
                       "AAVE", "CRV", "bitcoin", "ethereum", "defi", "crypto", "token"]
    
    found_tokens = []
    trend_lower = trend_data.lower()
    
    for keyword in crypto_keywords[:10]:  # Check first 10
        if keyword.lower() in trend_lower:
            found_tokens.append(keyword.upper())
    
    # Remove duplicates and limit to 5
    found_tokens = list(set(found_tokens))[:5]
    
    # Build structured Telegram post
    if found_tokens:
        tokens_list = " | ".join(found_tokens)
        telegram_post = f"""🚀 DeFi Market Update

📊 Trending: {tokens_list}

📈 {tweet_text.split('#')[0].strip()}

💡 Stay ahead with real-time DeFi insights and AI-powered automation.

#DeFi #Crypto #YieldBot #FinancialFreedom"""
    else:
        # Fallback when no crypto tokens found
        telegram_post = f"""🚀 DeFi Market Update

{tweet_text}

📊 Stay informed about the latest trends in DeFi and crypto.

💡 AI-powered insights for smarter financial decisions.

#DeFi #Crypto #YieldBot #FinancialFreedom"""
    
    # Ensure it's not too long for Telegram (aim for 500-800 chars)
    if len(telegram_post) > 1000:
        telegram_post = telegram_post[:997] + "..."
    
    logger.info("Telegram post generated: %d chars", len(telegram_post))
    return telegram_post


def post_telegram_node(state: AgentState) -> dict:
    """Post crypto market update to Telegram group.
    
    Args:
        state: Current agent state with trend_data and tweet_text.
        
    Returns:
        Dictionary with telegram_status and telegram_message.
    """
    logger.info("---POSTING TO TELEGRAM---")
    
    trend_data = state.get("trend_data", "")
    tweet_text = state.get("tweet_text", "")
    image_url = state.get("image_url", "")
    
    if not tweet_text:
        logger.warning("No tweet text available, skipping Telegram post")
        return {
            "telegram_status": "Skipped: No content",
            "telegram_message": ""
        }
    
    try:
        # Convert to Telegram crypto format (sub-agent processes data)
        telegram_message = convert_to_telegram_crypto_post(trend_data, tweet_text)
        logger.info("Telegram message formatted: %s", telegram_message[:100])
        
        # Send to Telegram group
        if image_url:
            # Try sending with photo
            result = telegram_agent.send_photo(
                chat_id=telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID,
                photo=image_url,
                caption=telegram_message
            )
            if not result.get('success'):
                # Fallback to text-only if image fails
                logger.warning("Image send failed, sending text only")
                result = telegram_agent.send_to_group(telegram_message)
        else:
            # Send text only
            result = telegram_agent.send_to_group(telegram_message)
        
        if result.get('success'):
            msg_data = result.get('data', {}).get('result', {})
            message_id = msg_data.get('message_id', 'N/A')
            logger.info("✅ Telegram post successful: message_id=%s", message_id)
            return {
                "telegram_status": f"Posted: message_id={message_id}",
                "telegram_message": telegram_message
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error("❌ Telegram post failed: %s", error_msg)
            return {
                "telegram_status": f"Failed: {error_msg}",
                "telegram_message": telegram_message
            }
            
    except Exception as e:
        logger.exception("Telegram post error: %s", e)
        return {
            "telegram_status": f"Error: {str(e)}",
            "telegram_message": ""
        }


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

        # Add photo by downloading from URL or using local path
        if image_url and image_url.strip():
            if image_url.startswith("file:///"):
                # Local file from Hugging Face
                local_image_path = image_url.replace("file:///", "").replace("/", chr(92))
                if os.path.exists(local_image_path):
                    facebook_params["photo"] = local_image_path
                    logger.info("Facebook photo attached using HF local path: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_PHOTO_POST"
                else:
                    logger.error("Local image file not found: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_POST"
            elif image_url.startswith("https://"):
                # Remote URL (legacy Gemini)
                local_image_path = _download_image_from_url(image_url)
                if local_image_path:
                    facebook_params["photo"] = local_image_path
                    logger.info("Facebook photo attached using downloaded path: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_PHOTO_POST"
                else:
                    logger.error("Failed to download image from URL: %s", image_url)
                    facebook_tool = "FACEBOOK_CREATE_POST"
            else:
                logger.info("Unknown image URL format, posting text-only to Facebook")
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
workflow.add_node("post_telegram", post_telegram_node)
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
workflow.add_edge("post_social_media", "post_telegram")
workflow.add_edge("post_telegram", "post_instagram")
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
        logger.info("Telegram: %s", final_state.get("telegram_status", "N/A"))
        logger.info("Twitter Reply: %s", final_state.get("twitter_reply_status", "N/A"))
        logger.info("Facebook Comment: %s", final_state.get("comment_status", "N/A"))
        logger.info("Blog Email: %s", final_state.get("blog_status", "N/A"))
        logger.info("Blog Title: %s", final_state.get("blog_title", "N/A"))

        if final_state.get("error"):
            logger.error("Error: %s", final_state.get("error"))

    except Exception:
        logger.exception("Agent execution failed")