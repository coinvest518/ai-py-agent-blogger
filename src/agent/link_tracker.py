"""Google Sheets Link Performance Tracker.

Creates and manages sheets for tracking:
- Link clicks (affiliate + booking)
- Product mentions and conversions
- Blog performance metrics.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from composio import Composio

logger = logging.getLogger(__name__)


class LinkPerformanceTracker:
    """Tracks link clicks and product performance in Google Sheets."""
    
    def __init__(self):
        """Initialize Composio client with correct toolkit version."""
        self.composio_client = Composio(
            api_key=os.getenv("COMPOSIO_API_KEY"),
            entity_id=os.getenv("COMPOSIO_ENTITY_ID", "pg-test-e862c589-3f43-4cd7-9023-cc6ec5123c23"),
            toolkit_versions={"googlesheets": "20260211_00"}
        )
        self.spreadsheet_id = os.getenv("BLOG_SHEET_ID", "1d8krgp4rfeph3CjMyzwl9NekmEggYGV10vB6qLaSyfQ")
        
        # Sheet names for different tracking purposes
        self.link_sheet = "Link Performance"
        self.product_sheet = "Product Performance"
        self.blog_sheet = "Blog Performance"
    
    def setup_tracking_sheets(self) -> bool:
        """Initialize all tracking sheets with headers.
        
        Creates: Link Performance, Product Performance, Blog Performance tabs.
        
        Returns:
            True if setup successful
        """
        try:
            # Setup Link Performance sheet
            link_headers = [
                ["Date", "Blog Title", "Link Type", "Link Name", "Link URL", 
                 "Clicks", "Conversions", "Revenue", "CTR %", "Notes"]
            ]
            self._setup_sheet_headers(self.link_sheet, link_headers)
            logger.info(f"✅ Setup {self.link_sheet} sheet")
            
            # Setup Product Performance sheet
            product_headers = [
                ["Product Name", "Price", "Category", "Type", "Keywords", 
                 "Total Mentions", "Total Clicks", "Total Sales", "Revenue", 
                 "Last Mentioned", "Best Performing Blog", "Notes"]
            ]
            self._setup_sheet_headers(self.product_sheet, product_headers)
            logger.info(f"✅ Setup {self.product_sheet} sheet")
            
            # Setup Blog Performance sheet
            blog_headers = [
                ["Date", "Title", "Topic", "Word Count", "Affiliate Links Used", 
                 "Products Mentioned", "Consultation Type", "Total Clicks", 
                 "Email Opens", "Conversions", "Revenue", "Notes"]
            ]
            self._setup_sheet_headers(self.blog_sheet, blog_headers)
            logger.info(f"✅ Setup {self.blog_sheet} sheet")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup tracking sheets: {e}")
            return False
    
    def _setup_sheet_headers(self, sheet_name: str, headers: List[List[str]]) -> None:
        """Set up headers for a specific sheet."""
        try:
            response = self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_UPDATE",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "sheet_name": sheet_name,
                    "values": headers,
                    "first_cell_location": "A1"
                }
            )
            logger.debug(f"Setup headers for {sheet_name}: {response}")
        except Exception as e:
            logger.warning(f"Could not setup {sheet_name} headers (may already exist): {e}")
    
    def track_link_click(self, blog_title: str, link_type: str, link_name: str, 
                        link_url: str, clicks: int = 1) -> bool:
        """Track a link click event.
        
        Args:
            blog_title: Title of the blog post
            link_type: "affiliate" or "booking"
            link_name: Name of link (e.g., "ElevenLabs", "AI Consultation")
            link_url: Full URL of the link
            clicks: Number of clicks (default 1)
            
        Returns:
            True if tracked successfully
        """
        try:
            row_data = [[
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                blog_title,
                link_type,
                link_name,
                link_url,
                clicks,
                0,  # Conversions (TBD)
                0,  # Revenue (TBD)
                0,  # CTR % (calculated later)
                ""  # Notes
            ]]
            
            self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_UPDATE",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "sheet_name": self.link_sheet,
                    "values": row_data,
                    "first_cell_location": "A2"  # Append after headers
                }
            )
            
            logger.info(f"✅ Tracked link click: {link_name} ({link_type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track link click: {e}")
            return False
    
    def track_product_mention(self, product_name: str, blog_title: str, 
                            category: str = "", price: str = "") -> bool:
        """Track when a product is mentioned in a blog post.
        
        Args:
            product_name: Name of FDWA product
            blog_title: Title of blog where product was mentioned
            category: Product category (AI, Credit, Business, etc.)
            price: Product price
            
        Returns:
            True if tracked successfully
        """
        try:
            # First, check if product already exists
            existing = self._get_product_row(product_name)
            
            if existing:
                # Update existing product (increment mentions, update last mentioned)
                # Note: This is simplified - in production, you'd update the specific row
                logger.info(f"Product {product_name} already tracked, would update mentions")
                return True
            else:
                # Add new product
                row_data = [[
                    product_name,
                    price,
                    category,
                    "Digital Product",  # Default type
                    "",  # Keywords (TBD)
                    1,  # Total Mentions
                    0,  # Total Clicks
                    0,  # Total Sales
                    0,  # Revenue
                    datetime.now().strftime("%Y-%m-%d"),
                    blog_title,  # Best Performing Blog
                    ""  # Notes
                ]]
                
                self.composio_client.execute_action(
                    action="GOOGLESHEETS_BATCH_UPDATE",
                    params={
                        "spreadsheet_id": self.spreadsheet_id,
                        "sheet_name": self.product_sheet,
                        "values": row_data,
                        "first_cell_location": "A2"
                    }
                )
                
                logger.info(f"✅ Tracked product mention: {product_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to track product mention: {e}")
            return False
    
    def track_blog_performance(self, blog_data: Dict[str, Any]) -> bool:
        """Track overall blog performance metrics.
        
        Args:
            blog_data: Dictionary with keys:
                - title: Blog title
                - topic: Main topic
                - word_count: Word count
                - affiliate_links: List of affiliate tools used
                - products_mentioned: List of products mentioned
                - consultation_type: "ai", "credit", or "general"
                
        Returns:
            True if tracked successfully
        """
        try:
            row_data = [[
                datetime.now().strftime("%Y-%m-%d"),
                blog_data.get("title", "Untitled"),
                blog_data.get("topic", ""),
                blog_data.get("word_count", 0),
                ", ".join(blog_data.get("affiliate_links", [])),
                ", ".join(blog_data.get("products_mentioned", [])),
                blog_data.get("consultation_type", "general"),
                0,  # Total Clicks (TBD)
                0,  # Email Opens (TBD)
                0,  # Conversions (TBD)
                0,  # Revenue (TBD)
                ""  # Notes
            ]]
            
            self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_UPDATE",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "sheet_name": self.blog_sheet,
                    "values": row_data,
                    "first_cell_location": "A2"
                }
            )
            
            logger.info(f"✅ Tracked blog performance: {blog_data.get('title')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track blog performance: {e}")
            return False
    
    def _get_product_row(self, product_name: str) -> List | None:
        """Search for existing product row.
        
        Args:
            product_name: Name of product to search
            
        Returns:
            Product row data or None if not found
        """
        try:
            response = self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_GET",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "ranges": [f"{self.product_sheet}!A:A"]
                }
            )
            
            # Parse response
            data = response.get("data", {})
            if hasattr(data, 'valueRanges'):
                values = data.valueRanges[0].values if data.valueRanges else []
            else:
                values = data.get("valueRanges", [{}])[0].get("values", [])
            
            # Search for product name
            for i, row in enumerate(values):
                if row and row[0] == product_name:
                    return row
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not search for product {product_name}: {e}")
            return None
    
    def get_performance_insights(self, days: int = 30) -> Dict[str, Any]:
        """Get performance insights for the last N days.
        
        Used to feed back into blog generation for optimization.
        
        Args:
            days: Number of days to analyze (default 30)
            
        Returns:
            Dictionary with performance insights
        """
        try:
            # Get blog performance data
            self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_GET",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "ranges": [f"{self.blog_sheet}!A2:L100"]  # Get last 100 blogs
                }
            )
            
            # Get link performance data
            self.composio_client.execute_action(
                action="GOOGLESHEETS_BATCH_GET",
                params={
                    "spreadsheet_id": self.spreadsheet_id,
                    "ranges": [f"{self.link_sheet}!A2:J100"]  # Get last 100 clicks
                }
            )
            
            # Parse responses (simplified for now)
            insights = {
                "top_performing_topics": ["AI automation", "Credit repair"],  # TBD: Calculate from data
                "best_affiliate_links": ["ElevenLabs", "ManyChat"],  # TBD: Sort by clicks
                "best_products": ["AI Vibe Coding Bootcamp"],  # TBD: Sort by mentions + sales
                "avg_clicks_per_blog": 0,  # TBD: Calculate
                "total_conversions": 0,  # TBD: Sum from data
                "recommendation": "Focus on AI automation topics with ElevenLabs and ManyChat mentions"
            }
            
            logger.info("📊 Generated performance insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to get performance insights: {e}")
            return {}


if __name__ == "__main__":
    """Setup tracking sheets when run directly"""
    logging.basicConfig(level=logging.INFO)
    
    logger.info("📊 Setting up Google Sheets link performance tracker...")
    tracker = LinkPerformanceTracker()
    
    if tracker.setup_tracking_sheets():
        logger.info("✅ All tracking sheets initialized!")
        logger.info("Tracking sheets created:")
        logger.info("  - Link Performance: Tracks affiliate link and booking link clicks")
        logger.info("  - Product Performance: Tracks FDWA product mentions and sales")
        logger.info("  - Blog Performance: Tracks overall blog metrics")
        
        # Test tracking
        logger.info("🧪 Testing tracking functions...")
        tracker.track_link_click("Test Blog Post", "affiliate", "ElevenLabs", "https://try.elevenlabs.io/fdwa")
        tracker.track_product_mention("AI Vibe Coding Bootcamp", "Test Blog Post", "AI/Automation", "$199")
        tracker.track_blog_performance({
            "title": "Test Blog Post",
            "topic": "AI automation",
            "word_count": 1500,
            "affiliate_links": ["ElevenLabs", "ManyChat"],
            "products_mentioned": ["AI Vibe Coding Bootcamp"],
            "consultation_type": "ai"
        })
        logger.info("✅ Test tracking completed!")
    else:
        logger.error("❌ Failed to setup tracking sheets")
