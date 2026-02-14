"""Direct Twitter API integration (no Composio) using OAuth 2.0 Bearer Token."""

import os
import requests
from requests_oauthlib import OAuth1
import logging

logger = logging.getLogger(__name__)


class TwitterDirectClient:
    """Direct Twitter API v2 client using Bearer Token (OAuth 2.0)."""
    
    def __init__(self):
        """Initialize with credentials from environment variables."""
        # Try Bearer Token first (OAuth 2.0 - simpler)
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        
        # Fallback to OAuth 1.0a if Bearer Token not available
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        
        # Determine auth method
        if self.bearer_token:
            self.auth_method = "bearer"
            logger.info("Using Bearer Token authentication (OAuth 2.0)")
        elif all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            self.auth_method = "oauth1"
            self.auth = OAuth1(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret
            )
            logger.info("Using OAuth 1.0a authentication")
        else:
            raise ValueError(
                "Missing Twitter credentials. Set either:\n"
                "  - TWITTER_BEARER_TOKEN (OAuth 2.0 - simpler), or\n"
                "  - TWITTER_API_KEY + TWITTER_API_SECRET + TWITTER_ACCESS_TOKEN + TWITTER_ACCESS_TOKEN_SECRET (OAuth 1.0a)"
            )
        
        self.base_url = "https://api.twitter.com/2"
    
    def create_tweet(self, text: str, media_ids: list = None) -> dict:
        """Create a tweet using Twitter API v2.
        
        Args:
            text: Tweet text (max 280 characters)
            media_ids: Optional list of media IDs to attach
            
        Returns:
            Dict with tweet data including 'id' and 'text'
            
        Raises:
            Exception if tweet creation fails
        """
        url = f"{self.base_url}/tweets"
        
        payload = {"text": text}
        
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        
        logger.info(f"Creating tweet: {text[:50]}...")
        
        # Use Bearer Token if available, otherwise OAuth 1.0a
        if self.auth_method == "bearer":
            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers)
        else:
            response = requests.post(
                url,
                auth=self.auth,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 201:
            data = response.json()
            tweet_id = data.get("data", {}).get("id")
            logger.info(f"✅ Tweet created successfully! ID: {tweet_id}")
            return data
        else:
            error_msg = response.text
            logger.error(f"❌ Twitter API error ({response.status_code}): {error_msg}")
            raise Exception(f"Twitter API error: {response.status_code} - {error_msg}")
    
    def upload_media(self, image_path: str) -> str:
        """Upload media to Twitter (v1.1 endpoint for media upload).
        
        Args:
            image_path: Path to image file
            
        Returns:
            Media ID string
        """
        url = "https://upload.twitter.com/1.1/media/upload.json"
        
        logger.info(f"Uploading media: {image_path}")
        
        with open(image_path, 'rb') as file:
            files = {"media": file}
            response = requests.post(
                url,
                auth=self.auth,
                files=files
            )
        
        if response.status_code == 200:
            media_id = response.json().get("media_id_string")
            logger.info(f"✅ Media uploaded successfully! ID: {media_id}")
            return media_id
        else:
            error_msg = response.text
            logger.error(f"❌ Media upload error ({response.status_code}): {error_msg}")
            raise Exception(f"Media upload error: {response.status_code} - {error_msg}")


def post_tweet_direct(text: str, image_path: str = None) -> dict:
    """Post a tweet directly to Twitter API (no Composio).
    
    Args:
        text: Tweet text
        image_path: Optional path to image
        
    Returns:
        Dict with tweet_id and tweet_url
    """
    client = TwitterDirectClient()
    
    # Upload media if provided
    media_ids = None
    if image_path and os.path.exists(image_path):
        try:
            media_id = client.upload_media(image_path)
            media_ids = [media_id]
        except Exception as e:
            logger.warning(f"Media upload failed, posting text-only: {e}")
    
    # Create tweet
    result = client.create_tweet(text, media_ids=media_ids)
    
    tweet_id = result.get("data", {}).get("id")
    tweet_url = f"https://twitter.com/user/status/{tweet_id}" if tweet_id else None
    
    return {
        "tweet_id": tweet_id,
        "tweet_url": tweet_url,
        "success": True
    }
