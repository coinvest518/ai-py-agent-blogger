"""Comprehensive duplicate detection for all social media posts."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# File to track all social media posts
SOCIAL_POSTS_FILE = Path(__file__).parent.parent.parent / "social_media_history.json"

# Import Google Sheets integration
try:
    from src.agent.sheets_agent import save_post_to_sheets
    SHEETS_ENABLED = True
except ImportError:
    logger.warning("Google Sheets integration not available")
    SHEETS_ENABLED = False

def _get_post_hash(content: str) -> str:
    """Generate a hash for content to detect duplicates."""
    normalized = content.lower().strip()
    # Remove URLs, mentions, hashtags for better duplicate detection
    import re
    normalized = re.sub(r'https?://\S+', '', normalized)
    normalized = re.sub(r'@\w+', '', normalized)
    normalized = re.sub(r'#\w+', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def _load_post_history() -> Dict:
    """Load social media post history."""
    if SOCIAL_POSTS_FILE.exists():
        try:
            with open(SOCIAL_POSTS_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load post history: {e}")
    
    return {
        "posts": [],
        "hashes": [],
        "last_updated": None
    }


def _save_post_history(data: Dict) -> None:
    """Save social media post history."""
    try:
        data["last_updated"] = datetime.now().isoformat()
        with open(SOCIAL_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save post history: {e}")


def is_duplicate_post(content: str, platform: str, lookback_days: int = 30) -> bool:
    """Check if this content was already posted on any platform recently.
    
    Args:
        content: The post content (tweet, caption, etc.)
        platform: Platform name (twitter, facebook, linkedin, instagram, telegram, blog)
        lookback_days: How many days to check back for duplicates
        
    Returns:
        True if duplicate found, False otherwise
    """
    try:
        history = _load_post_history()
        content_hash = _get_post_hash(content)
        
        # Check if exact same content hash exists
        if content_hash in history.get("hashes", []):
            logger.warning(f"⚠️  Duplicate content detected for {platform}!")
            logger.warning(f"   Content: {content[:100]}...")
            return True
        
        # Check recent posts for similarity
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_posts = [
            p for p in history.get("posts", [])
            if datetime.fromisoformat(p["timestamp"]) > cutoff_date
        ]
        
        # Check for very similar content (first 200 chars)
        content_preview = content[:200].lower().strip()
        for post in recent_posts:
            if post.get("content_preview", "").lower().strip() == content_preview:
                logger.warning(f"⚠️  Very similar content found for {platform} from {post['timestamp']}")
                logger.warning(f"   Previous: {post['content_preview'][:100]}...")
                logger.warning(f"   Current:  {content[:100]}...")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking duplicate: {e}")
        # Don't block posting if check fails
        return False


def record_post(content: str, platform: str, post_id: str | None = None, 
                image_url: str | None = None, metadata: Dict | None = None) -> None:
    """Record a posted content to prevent future duplicates.
    
    Args:
        content: The post content
        platform: Platform name
        post_id: Platform-specific post ID
        image_url: URL of attached image
        metadata: Additional metadata
    """
    try:
        history = _load_post_history()
        
        post_record = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "content_hash": _get_post_hash(content),
            "content_preview": content[:200],
            "post_id": post_id,
            "image_url": image_url,
            "metadata": metadata or {}
        }
        
        # Add to posts list
        history.setdefault("posts", []).append(post_record)
        
        # Add hash to quick lookup list
        history.setdefault("hashes", []).append(post_record["content_hash"])
        
        # Keep only last 1000 posts (prevent file bloat)
        if len(history["posts"]) > 1000:
            # Remove oldest posts
            removed_posts = history["posts"][:-1000]
            history["posts"] = history["posts"][-1000:]
            
            # Remove their hashes
            removed_hashes = {p["content_hash"] for p in removed_posts}
            history["hashes"] = [h for h in history["hashes"] if h not in removed_hashes]
        
        _save_post_history(history)
        logger.info(f"✓ Recorded {platform} post to history (Total: {len(history['posts'])})")
        
        # Also save to Google Sheets for persistent cloud storage
        if SHEETS_ENABLED:
            try:
                save_post_to_sheets(
                    platform=platform,
                    content=content,
                    post_id=post_id or "",
                    image_url=image_url or "",
                    metadata=metadata
                )
            except Exception as sheets_error:
                logger.warning(f"Failed to save to Google Sheets: {sheets_error}")
        
    except Exception as e:
        logger.error(f"Failed to record post: {e}")


def get_recent_posts(platform: str | None = None, limit: int = 10) -> List[Dict]:
    """Get recent posts, optionally filtered by platform.
    
    Args:
        platform: Filter by platform (None = all)
        limit: Maximum number of posts to return
        
    Returns:
        List of recent post records
    """
    try:
        history = _load_post_history()
        posts = history.get("posts", [])
        
        if platform:
            posts = [p for p in posts if p.get("platform") == platform]
        
        # Sort by timestamp (newest first)
        posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)
        
        return posts[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get recent posts: {e}")
        return []


def clear_old_posts(days: int = 90) -> int:
    """Clear posts older than specified days.
    
    Args:
        days: Remove posts older than this many days
        
    Returns:
        Number of posts removed
    """
    try:
        history = _load_post_history()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        old_posts = [
            p for p in history.get("posts", [])
            if datetime.fromisoformat(p["timestamp"]) <= cutoff_date
        ]
        
        if not old_posts:
            logger.info("No old posts to remove")
            return 0
        
        # Keep only recent posts
        history["posts"] = [
            p for p in history.get("posts", [])
            if datetime.fromisoformat(p["timestamp"]) > cutoff_date
        ]
        
        # Rebuild hash list
        history["hashes"] = [p["content_hash"] for p in history["posts"]]
        
        _save_post_history(history)
        logger.info(f"Removed {len(old_posts)} posts older than {days} days")
        
        return len(old_posts)
        
    except Exception as e:
        logger.error(f"Failed to clear old posts: {e}")
        return 0


def get_stats() -> Dict:
    """Get statistics about post history.
    
    Returns:
        Dictionary with stats
    """
    try:
        history = _load_post_history()
        posts = history.get("posts", [])
        
        # Count by platform
        platform_counts = {}
        for post in posts:
            platform = post.get("platform", "unknown")
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Get date range
        if posts:
            timestamps = [datetime.fromisoformat(p["timestamp"]) for p in posts]
            oldest = min(timestamps)
            newest = max(timestamps)
        else:
            oldest = newest = None
        
        return {
            "total_posts": len(posts),
            "unique_hashes": len(set(history.get("hashes", []))),
            "platform_counts": platform_counts,
            "oldest_post": oldest.isoformat() if oldest else None,
            "newest_post": newest.isoformat() if newest else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}
