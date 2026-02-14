"""
Medium Blog Scraper - Extract FDWA writing samples from Medium
Scrapes https://medium.com/@coinvestinc to learn writing style, tone, and successful topics
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def scrape_medium_profile(username: str = "coinvestinc", max_posts: int = 10) -> List[Dict[str, Any]]:
    """
    Scrape Medium profile to extract blog posts and writing style.
    
    Args:
        username: Medium username (default: coinvestinc)
        max_posts: Maximum number of posts to scrape (default: 10)
        
    Returns:
        List of dictionaries with post data (title, url, date, excerpt, full_text)
    """
    profile_url = f"https://medium.com/@{username}"
    posts_data = []
    
    try:
        # Fetch profile page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(profile_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Medium uses dynamic loading, so we'll try to extract from HTML
        # Look for article links in the profile
        article_links = []
        
        # Find all article links (Medium structure may vary)
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/@' in href and username in href and href not in article_links:
                # Construct full URL if relative
                if href.startswith('/'):
                    href = f"https://medium.com{href}"
                if href not in [p['url'] for p in posts_data]:
                    article_links.append(href)
        
        logger.info(f"Found {len(article_links)} article links on profile")
        
        # Scrape individual articles (limit to max_posts)
        for i, article_url in enumerate(article_links[:max_posts]):
            try:
                logger.info(f"Scraping article {i+1}/{min(len(article_links), max_posts)}: {article_url}")
                post_data = scrape_medium_article(article_url)
                if post_data:
                    posts_data.append(post_data)
            except Exception as e:
                logger.warning(f"Failed to scrape {article_url}: {e}")
                continue
        
        logger.info(f"Successfully scraped {len(posts_data)} posts from Medium")
        return posts_data
        
    except Exception as e:
        logger.error(f"Failed to scrape Medium profile: {e}")
        return []


def scrape_medium_article(url: str) -> Optional[Dict[str, Any]]:
    """
    Scrape a single Medium article.
    
    Args:
        url: Full URL to Medium article
        
    Returns:
        Dictionary with article data or None if failed
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_tag = soup.find('h1') or soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "No title"
        
        # Extract date (Medium uses various formats)
        date_str = None
        date_tag = soup.find('time')
        if date_tag:
            date_str = date_tag.get('datetime') or date_tag.get_text(strip=True)
        
        # Extract excerpt (first paragraph or meta description)
        excerpt = ""
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            excerpt = meta_desc.get('content', '')
        else:
            first_p = soup.find('p')
            if first_p:
                excerpt = first_p.get_text(strip=True)[:200]
        
        # Extract full text (all paragraphs)
        paragraphs = soup.find_all('p')
        full_text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # Extract word count
        word_count = len(full_text.split())
        
        return {
            'title': title,
            'url': url,
            'date': date_str,
            'excerpt': excerpt,
            'full_text': full_text,
            'word_count': word_count,
            'scraped_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to scrape article {url}: {e}")
        return None


def save_medium_samples(posts_data: List[Dict[str, Any]], output_file: str = "medium_writing_samples.json") -> None:
    """
    Save scraped Medium posts to JSON file.
    
    Args:
        posts_data: List of post dictionaries
        output_file: Output filename (default: medium_writing_samples.json)
    """
    output_path = Path(__file__).parent.parent.parent / output_file
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'source': 'Medium @coinvestinc',
                'scraped_at': datetime.now().isoformat(),
                'total_posts': len(posts_data),
                'posts': posts_data
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(posts_data)} Medium posts to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to save Medium samples: {e}")


def analyze_writing_style(posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze writing style from scraped posts.
    
    Args:
        posts_data: List of post dictionaries
        
    Returns:
        Dictionary with style analysis
    """
    if not posts_data:
        return {}
    
    # Calculate averages
    word_counts = [post['word_count'] for post in posts_data if 'word_count' in post]
    avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0
    
    # Extract common themes (simple keyword frequency)
    all_text = ' '.join([post.get('full_text', '') for post in posts_data]).lower()
    
    # Common FDWA-related keywords to track
    keywords = {
        'ai': all_text.count('ai '),
        'automation': all_text.count('automation'),
        'credit': all_text.count('credit'),
        'business': all_text.count('business'),
        'entrepreneur': all_text.count('entrepreneur'),
        'digital': all_text.count('digital'),
        'wealth': all_text.count('wealth'),
        'strategy': all_text.count('strategy')
    }
    
    return {
        'total_posts_analyzed': len(posts_data),
        'avg_word_count': int(avg_word_count),
        'keyword_frequency': keywords,
        'most_common_topics': sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:5]
    }


if __name__ == "__main__":
    """Run Medium scraper when executed directly"""
    logging.basicConfig(level=logging.INFO)
    
    logger.info("🔍 Scraping FDWA Medium blog (@coinvestinc)...")
    posts = scrape_medium_profile(username="coinvestinc", max_posts=10)
    
    if posts:
        logger.info("✅ Scraped %d posts", len(posts))
        
        # Save to JSON
        save_medium_samples(posts)
        logger.info("💾 Saved to medium_writing_samples.json")
        
        # Analyze style
        analysis = analyze_writing_style(posts)
        logger.info("📊 Writing Style Analysis:")
        logger.info("Average word count: %s", analysis.get('avg_word_count', 0))
        logger.info("Most common topics: %s", analysis.get('most_common_topics', []))
    else:
        logger.error("❌ Failed to scrape Medium posts")
        logger.info("💡 Note: Medium uses JavaScript rendering. Consider using Selenium or Playwright for better scraping.")
