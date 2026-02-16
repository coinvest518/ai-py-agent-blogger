"""Google Sheets integration for tracking posts and crypto tokens.

This module provides AI agents with persistent storage in Google Sheets for:
1. Social media posts tracking (prevent duplicates, analytics)
2. Crypto tokens from Telegram (mentioned tokens, prices, trends)
3. Searchable history for AI decision-making
"""

import logging
import os
import re
from datetime import datetime
from typing import Dict, List

from composio import Composio
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Composio client
# Set toolkit version for googlesheets app (required for manual tool execution)
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id=os.getenv("GOOGLESHEETS_USER_ID"),
    toolkit_versions={"googlesheets": "20260211_00"}
)

# Spreadsheet IDs (will be created if not exist)
POSTS_SHEET_ID = os.getenv("GOOGLESHEETS_POSTS_SPREADSHEET_ID")
TOKENS_SHEET_ID = os.getenv("GOOGLESHEETS_TOKENS_SPREADSHEET_ID")


class GoogleSheetsAgent:
    """Sub-agent for managing Google Sheets storage."""
    
    def __init__(self):
        """Initialize Google Sheets agent with credentials."""
        self.account_id = os.getenv("GOOGLESHEETS_ACCOUNT_ID")
        self.posts_sheet_id = POSTS_SHEET_ID
        self.tokens_sheet_id = TOKENS_SHEET_ID
        # cache discovered tool slugs to avoid repeated API calls
        self._discovered_create_slug: str | None = None
        
    def _execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """Execute a Composio Google Sheets tool (simple wrapper)."""
        try:
            response = composio_client.tools.execute(
                tool_name,
                params,
                connected_account_id=self.account_id
            )
            return response
        except Exception as e:
            logger.error(f"Google Sheets tool error ({tool_name}): {e}")
            return {"successful": False, "error": str(e)}

    def _discover_sheets_create_tool(self) -> str | None:
        """Discover the available 'create' tool slug for Google Sheets in Composio.

        Returns the preferred slug (e.g. GOOGLESHEETS_CREATE_GOOGLE_SHEET1) if
        present, otherwise returns any matching create-tool slug found, or None.
        """
        if self._discovered_create_slug:
            return self._discovered_create_slug

        try:
            tools = composio_client.tools.list(limit=200)
            candidate = None
            for t in tools:
                slug = t.get("slug") or t.get("name")
                if not slug:
                    continue
                if "GOOGLESHEETS" in slug.upper() and "CREATE" in slug.upper():
                    # prefer the explicit '..._CREATE_GOOGLE_SHEET1' slug when present
                    if slug.upper().startswith("GOOGLESHEETS_CREATE_GOOGLE_SHEET1"):
                        candidate = slug
                        break
                    if not candidate:
                        candidate = slug

            if candidate:
                self._discovered_create_slug = candidate
                logger.debug(f"Discovered Google Sheets create-tool slug: {candidate}")
                return candidate

        except Exception as e:
            logger.debug(f"Could not list Composio tools for discovery: {e}")

        return None
    def _create_sheet_with_fallback(self, title: str, locale: str = "en_US") -> str | None:
        """Create a Google Sheet using the first available tool slug.

        Tries multiple known tool slugs (backwards-compatible) and returns the
        spreadsheetId on success or None on failure. Does not pass unexpected
        kwargs to composio.tools.execute.
        """
        candidate_slugs = [
            "GOOGLESHEETS_CREATE_GOOGLE_SHEET1",
            "GOOGLESHEETS_CREATE_GOOGLE_SHEET",
            "GOOGLESHEETS_CREATE_GOOGLE_SHEET_V2",
            "GOOGLESHEETS_CREATE_SHEET",
        ]

        # prefer a discovered (exact) slug if available
        discovered = self._discover_sheets_create_tool()
        if discovered:
            candidate_slugs = [discovered] + [s for s in candidate_slugs if s != discovered]

        for slug in candidate_slugs:
            try:
                logger.debug(f"Attempting sheet create with tool: {slug}")

                # Toolkit version is already set globally in composio_client initialization
                resp = self._execute_tool(slug, {"title": title, "locale": locale})

                if resp.get("successful"):
                    sid = resp.get("data", {}).get("spreadsheetId")
                    logger.info(f"✓ Created spreadsheet via {slug}: {sid}")
                    return sid
                else:
                    logger.debug(f"Tool {slug} responded but did not succeed: {resp.get('error')}")
            except Exception as e:
                logger.debug(f"Tool {slug} raised error: {e}")

        logger.error("All configured Google Sheets create-tool slugs failed or are unavailable.")
        return None

    def create_posts_spreadsheet(self) -> str | None:
        """Create a new spreadsheet for tracking social media posts (fallback-aware)."""
        try:
            logger.info("Creating Social Media Posts tracking spreadsheet (fallback-aware)...")
            sheet_id = self._create_sheet_with_fallback("FDWA AI Agent - Social Media Posts", "en_US")

            if sheet_id:
                # Rename default "Sheet1" to "AI Agent Memory"
                self._rename_sheet_tab(sheet_id, "Sheet1", "AI Agent Memory")
                # Set up headers
                self._setup_posts_headers(sheet_id)
                return sheet_id

            logger.error("Failed to create posts spreadsheet with available tool slugs")
            return None

        except Exception as e:
            logger.exception(f"Error creating posts spreadsheet: {e}")
            return None
    
    def _setup_posts_headers(self, sheet_id: str):
        """Set up column headers for posts sheet."""
        headers = [
            ["Timestamp", "Platform", "Content Preview", "Post ID", "Image URL", 
             "Engagement", "Status", "Hash", "Full Content"]
        ]
        
        try:
            self._execute_tool(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": sheet_id,
                    "requests": [{
                        "updateCells": {
                            "range": {
                                "sheetId": 0,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": 9
                            },
                            "rows": [{
                                "values": [
                                    {"userEnteredValue": {"stringValue": h}} 
                                    for h in headers[0]
                                ]
                            }],
                            "fields": "userEnteredValue"
                        }
                    }]
                }
            )
            logger.info("✓ Set up posts sheet headers")
        except Exception as e:
            logger.error(f"Failed to set up headers: {e}")
    
    def create_tokens_spreadsheet(self) -> str | None:
        """Create a new spreadsheet for tracking crypto tokens (fallback-aware)."""
        try:
            logger.info("Creating Crypto Tokens tracking spreadsheet (fallback-aware)...")
            sheet_id = self._create_sheet_with_fallback("FDWA AI Agent - Crypto Tokens", "en_US")

            if sheet_id:
                # Rename default "Sheet1" to "AI Agent Memory"
                self._rename_sheet_tab(sheet_id, "Sheet1", "AI Agent Memory")
                # Set up headers
                self._setup_tokens_headers(sheet_id)
                return sheet_id

            logger.error("Failed to create tokens spreadsheet with available tool slugs")
            return None

        except Exception as e:
            logger.exception(f"Error creating tokens spreadsheet: {e}")
            return None
    
    def _setup_tokens_headers(self, sheet_id: str):
        """Set up column headers for tokens sheet with AI analysis."""
        headers = [
            ["Timestamp", "Token Symbol", "Token Name", "Price", "24h Change %", "Volume 24h", "Market Cap",
             "Trade Score", "Profit Prob %", "Risk Level", "Trading Signal", "Momentum", "Liquidity",
             "Source", "AI Reasoning", "Notes"]
        ]
        
        try:
            self._execute_tool(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": sheet_id,
                    "requests": [{
                        "updateCells": {
                            "range": {
                                "sheetId": 0,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": 16
                            },
                            "rows": [{
                                "values": [
                                    {"userEnteredValue": {"stringValue": h}} 
                                    for h in headers[0]
                                ]
                            }],
                            "fields": "userEnteredValue"
                        }
                    }]
                }
            )
            logger.info("✓ Set up tokens sheet headers")
        except Exception as e:
            logger.error(f"Failed to set up headers: {e}")
    
    def save_post(self, platform: str, content: str, post_id: str = "", 
                  image_url: str = "", metadata: Dict | None = None) -> bool:
        """Save a social media post to Google Sheets.
        
        Auto-creates new sheet if current one hits 10M cell limit.
        
        Args:
            platform: Platform name (twitter, facebook, linkedin, etc.)
            content: Post content/text
            post_id: Platform-specific post ID
            image_url: URL of attached image
            metadata: Additional metadata dict
            
        Returns:
            True if saved successfully
        """
        if not self.posts_sheet_id:
            logger.warning("Posts spreadsheet not configured, skipping Sheets save")
            return False
        
        # Try to save, with auto-recovery if cell limit hit
        for attempt in range(2):  # Try twice: original + retry after new sheet
            try:
                # Create row data
                timestamp = datetime.now().isoformat()
                content_preview = content[:200]
                content_hash = self._get_content_hash(content)
                
                row_data = [
                    timestamp,
                    platform.upper(),
                    content_preview,
                    post_id or "N/A",
                    image_url or "",
                    metadata.get("engagement", "") if metadata else "",
                    "Posted",
                    content_hash,
                    content
                ]
                
                # Append to sheet using batch_update
                # Try different sheet names with fallback chain: Posts Tracking → AI Agent Memory → Sheet1
                sheet_name = "Posts Tracking"  # New sheets use this name
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": self.posts_sheet_id,
                        "sheet_name": sheet_name,
                        "values": [row_data]
                    }
                )
                
                # Fallback to "AI Agent Memory" (legacy sheets)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.posts_sheet_id,
                            "sheet_name": "AI Agent Memory",
                            "values": [row_data]
                        }
                    )
                
                # Final fallback to "Sheet1" (brand new/unconfigured sheets)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.posts_sheet_id,
                            "sheet_name": "Sheet1",
                            "values": [row_data]
                        }
                    )
                
                if response.get("successful"):
                    logger.info(f"✓ Saved {platform} post to Google Sheets")
                    return True
                else:
                    error_msg = response.get('error', '')
                    
                    # Check if cell limit error
                    if attempt == 0 and self._is_cell_limit_error(error_msg):
                        logger.warning("⚠️ Posts sheet hit cell limit, creating new sheet...")
                        new_sheet_id = self._create_new_posts_sheet_and_update_env()
                        if new_sheet_id:
                            logger.info("🔄 Retrying save with new sheet...")
                            continue  # Retry with new sheet
                    
                    logger.error(f"Failed to save post: {error_msg}")
                    return False
                    
            except Exception as e:
                error_msg = str(e)
                
                # Check if cell limit error in exception
                if attempt == 0 and self._is_cell_limit_error(error_msg):
                    logger.warning("⚠️ Posts sheet hit cell limit (exception), creating new sheet...")
                    new_sheet_id = self._create_new_posts_sheet_and_update_env()
                    if new_sheet_id:
                        logger.info("🔄 Retrying save with new sheet...")
                        continue  # Retry with new sheet
                
                logger.exception(f"Error saving post to Sheets: {e}")
                return False
        
        return False
    
    def save_crypto_token(self, symbol: str, name: str = "", 
                         price: str = "", percent_change_24h: str = "",
                         volume_24h: str = "", market_cap: str = "",
                         trade_score: str = "", profit_probability: str = "",
                         risk_level: str = "", trading_signal: str = "",
                         momentum: str = "", liquidity: str = "",
                         source: str = "ai_analysis",
                         reasoning: str = "", notes: str = "") -> bool:
        """Save an AI-analyzed crypto token to Google Sheets.
        
        Auto-creates new sheet if current one hits 10M cell limit.
        
        Args:
            symbol: Token symbol (e.g., BTC, ETH, DOGE)
            name: Full token name
            price: Current price (USD)
            percent_change_24h: 24h percentage change
            volume_24h: 24h trading volume
            market_cap: Market capitalization
            trade_score: AI trade score (0-100)
            profit_probability: Profit probability (0-100%)
            risk_level: Risk assessment (LOW/MEDIUM/HIGH)
            trading_signal: Trading signal (STRONG_BUY, BUY, HOLD, etc.)
            momentum: Momentum strength (STRONG, MODERATE, WEAK, etc.)
            liquidity: Liquidity quality (EXCELLENT, GOOD, FAIR, POOR)
            source: Data source (default: ai_analysis)
            reasoning: AI reasoning for selecting this token
            notes: Additional notes
            
        Returns:
            True if saved successfully
        """
        if not self.tokens_sheet_id:
            logger.warning("Tokens spreadsheet not configured, skipping Sheets save")
            return False
        
        # Try to save, with auto-recovery if cell limit hit
        for attempt in range(2):  # Try twice: original + retry after new sheet
            try:
                timestamp = datetime.now().isoformat()
                
                row_data = [
                    timestamp,
                    symbol.upper(),
                    name,
                    price,
                    percent_change_24h,
                    volume_24h,
                    market_cap,
                    trade_score,
                    profit_probability,
                    risk_level,
                    trading_signal,
                    momentum,
                    liquidity,
                    source,
                    reasoning,
                    notes
                ]
                
                # Append to sheet using batch_update
                # Try different sheet names with fallback chain: Token Tracking → AI Agent Memory → Sheet1
                sheet_name = "Token Tracking"  # New sheets use this name
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": self.tokens_sheet_id,
                        "sheet_name": sheet_name,
                        "values": [row_data]
                    }
                )
                
                # Fallback to "AI Agent Memory" (legacy sheets)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.tokens_sheet_id,
                            "sheet_name": "AI Agent Memory",
                            "values": [row_data]
                        }
                    )
                
                # Final fallback to "Sheet1" (brand new/unconfigured sheets)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.tokens_sheet_id,
                            "sheet_name": "Sheet1",
                            "values": [row_data]
                        }
                    )
                
                if response.get("successful"):
                    logger.info(f"✓ Saved {symbol} token to Google Sheets")
                    return True
                else:
                    error_msg = response.get('error', '')
                    
                    # Check if cell limit error
                    if attempt == 0 and self._is_cell_limit_error(error_msg):
                        logger.warning("⚠️ Tokens sheet hit cell limit, creating new sheet...")
                        new_sheet_id = self._create_new_tokens_sheet_and_update_env()
                        if new_sheet_id:
                            logger.info("🔄 Retrying save with new sheet...")
                            continue  # Retry with new sheet
                    
                    logger.error(f"Failed to save token: {error_msg}")
                    return False
                    
            except Exception as e:
                error_msg = str(e)
                
                # Check if cell limit error in exception
                if attempt == 0 and self._is_cell_limit_error(error_msg):
                    logger.warning("⚠️ Tokens sheet hit cell limit (exception), creating new sheet...")
                    new_sheet_id = self._create_new_tokens_sheet_and_update_env()
                    if new_sheet_id:
                        logger.info("🔄 Retrying save with new sheet...")
                        continue  # Retry with new sheet
                
                logger.exception(f"Error saving token to Sheets: {e}")
                return False
        
        return False
    
    def save_crypto_tokens_batch(self, tokens: list[dict]) -> int:
        """Save multiple crypto tokens to Google Sheets in a single API call.

        Each token dict should have keys matching save_crypto_token() params:
        symbol, name, price, percent_change_24h, volume_24h, market_cap,
        trade_score, profit_probability, risk_level, trading_signal,
        momentum, liquidity, source, reasoning, notes.

        Returns:
            Number of tokens saved (0 if any error).
        """
        if not self.tokens_sheet_id or not tokens:
            return 0

        timestamp = datetime.now().isoformat()
        rows = []
        for t in tokens:
            rows.append([
                timestamp,
                str(t.get("symbol", "?")).upper(),
                str(t.get("name", "")),
                str(t.get("price", "")),
                str(t.get("percent_change_24h", "")),
                str(t.get("volume_24h", "")),
                str(t.get("market_cap", "")),
                str(t.get("trade_score", "")),
                str(t.get("profit_probability", "")),
                str(t.get("risk_level", "")),
                str(t.get("trading_signal", "")),
                str(t.get("momentum", "")),
                str(t.get("liquidity", "")),
                str(t.get("source", "ai_analysis")),
                str(t.get("reasoning", "")),
                str(t.get("notes", "")),
            ])

        for sheet_name in ("Token Tracking", "AI Agent Memory", "Sheet1"):
            try:
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": self.tokens_sheet_id,
                        "sheet_name": sheet_name,
                        "values": rows,
                    },
                )
                if response.get("successful"):
                    logger.info("✓ Batch-saved %d tokens to sheet '%s'", len(rows), sheet_name)
                    return len(rows)
                if "not found" not in str(response.get("error", "")).lower():
                    logger.error("Batch token save failed: %s", response.get("error"))
                    return 0
            except Exception as e:
                if "not found" not in str(e).lower():
                    logger.exception("Batch token save error: %s", e)
                    return 0

        logger.error("Could not find any valid sheet tab for batch token save")
        return 0

    def search_posts(self, platform: str | None = None, 
                    days_back: int = 30, limit: int = 100) -> List[Dict]:
        """Search recent posts from Google Sheets.
        
        Args:
            platform: Filter by platform (None = all)
            days_back: How many days to look back
            limit: Maximum results
            
        Returns:
            List of post dictionaries
        """
        if not self.posts_sheet_id:
            return []
        
        try:
            # Read all data using batch_get
            # Try different sheet names with fallback chain
            sheet_names_to_try = ["Posts Tracking", "AI Agent Memory", "Sheet1"]
            response = None
            
            for sheet_name in sheet_names_to_try:
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_GET",
                    {
                        "spreadsheet_id": self.posts_sheet_id,
                        "ranges": [f"{sheet_name}!A2:I1000"]  # Skip header, read up to 1000 rows
                    }
                )
                
                if response.get("successful"):
                    break  # Success, stop trying
                
                # If sheet not found, try next name
                if "not found" in str(response.get('error', '')).lower():
                    continue
                else:
                    # Other error, don't retry
                    break
            
            if not response or not response.get("successful"):
                return []
            
            # GOOGLESHEETS_BATCH_GET returns data.valueRanges[0].values
            value_ranges = response.get("data", {}).get("valueRanges", [])
            values = value_ranges[0].get("values", []) if value_ranges else []
            posts = []
            
            for row in values:
                if len(row) < 4:
                    continue
                
                post = {
                    "timestamp": row[0] if len(row) > 0 else "",
                    "platform": row[1] if len(row) > 1 else "",
                    "content_preview": row[2] if len(row) > 2 else "",
                    "post_id": row[3] if len(row) > 3 else "",
                    "image_url": row[4] if len(row) > 4 else "",
                    "engagement": row[5] if len(row) > 5 else "",
                    "status": row[6] if len(row) > 6 else "",
                    "hash": row[7] if len(row) > 7 else "",
                    "full_content": row[8] if len(row) > 8 else ""
                }
                
                # Filter by platform if specified
                if platform and post["platform"].lower() != platform.lower():
                    continue
                
                posts.append(post)
                
                if len(posts) >= limit:
                    break
            
            logger.info(f"Found {len(posts)} posts in Google Sheets")
            return posts
            
        except Exception as e:
            logger.exception(f"Error searching posts: {e}")
            return []
    
    def search_tokens(self, symbol: str | None = None, 
                     source: str | None = None, limit: int = 100) -> List[Dict]:
        """Search crypto tokens from Google Sheets.
        
        Args:
            symbol: Filter by token symbol
            source: Filter by source (telegram, twitter, etc.)
            limit: Maximum results
            
        Returns:
            List of token dictionaries
        """
        if not self.tokens_sheet_id:
            return []
        
        try:
            # Read all data using batch_get
            # Try different sheet names with fallback chain
            sheet_names_to_try = ["Token Tracking", "AI Agent Memory", "Sheet1"]
            response = None
            
            for sheet_name in sheet_names_to_try:
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_GET",
                    {
                        "spreadsheet_id": self.tokens_sheet_id,
                        "ranges": [f"{sheet_name}!A2:P1000"]  # Skip header (16 columns)
                    }
                )
                
                if response.get("successful"):
                    break  # Success, stop trying
                
                # If sheet not found, try next name
                if "not found" in str(response.get('error', '')).lower():
                    continue
                else:
                    # Other error, don't retry
                    break
            
            if not response or not response.get("successful"):
                return []
            
            # GOOGLESHEETS_BATCH_GET returns data.valueRanges[0].values
            value_ranges = response.get("data", {}).get("valueRanges", [])
            values = value_ranges[0].get("values", []) if value_ranges else []
            tokens = []
            
            for row in values:
                if len(row) < 2:
                    continue
                
                token = {
                    "timestamp": row[0] if len(row) > 0 else "",
                    "symbol": row[1] if len(row) > 1 else "",
                    "name": row[2] if len(row) > 2 else "",
                    "price": row[3] if len(row) > 3 else "",
                    "percent_change_24h": row[4] if len(row) > 4 else "",
                    "volume_24h": row[5] if len(row) > 5 else "",
                    "market_cap": row[6] if len(row) > 6 else "",
                    "trade_score": row[7] if len(row) > 7 else "",
                    "profit_probability": row[8] if len(row) > 8 else "",
                    "risk_level": row[9] if len(row) > 9 else "",
                    "trading_signal": row[10] if len(row) > 10 else "",
                    "momentum": row[11] if len(row) > 11 else "",
                    "liquidity": row[12] if len(row) > 12 else "",
                    "source": row[13] if len(row) > 13 else "",
                    "reasoning": row[14] if len(row) > 14 else "",
                    "notes": row[15] if len(row) > 15 else ""
                }
                
                # Filter by symbol
                if symbol and token["symbol"].lower() != symbol.lower():
                    continue
                
                # Filter by source
                if source and token["source"].lower() != source.lower():
                    continue
                
                tokens.append(token)
                
                if len(tokens) >= limit:
                    break
            
            logger.info(f"Found {len(tokens)} tokens in Google Sheets")
            return tokens
            
        except Exception as e:
            logger.exception(f"Error searching tokens: {e}")
            return []
    
    def setup_headers(self) -> Dict[str, bool]:
        """Set up column headers in both sheets (posts and tokens).
        
        Call this once when using a new/blank spreadsheet.
        
        Returns:
            Dict with 'posts' and 'tokens' keys indicating success
        """
        results = {"posts": False, "tokens": False}
        
        # Setup posts sheet headers
        if self.posts_sheet_id:
            try:
                headers = [
                    ["Timestamp", "Platform", "Content Preview", "Post ID", "Image URL", 
                     "Engagement", "Status", "Hash", "Full Content"]
                ]
                
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": self.posts_sheet_id,
                        "sheet_name": "Posts Tracking",
                        "values": headers,
                        "first_cell_location": "A1"
                    }
                )
                
                # Try old name if new name fails (backwards compatibility)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.posts_sheet_id,
                            "sheet_name": "AI Agent Memory",
                            "values": headers,
                            "first_cell_location": "A1"
                        }
                    )
                
                if response.get("successful"):
                    logger.info("✓ Posts sheet headers set up")
                    results["posts"] = True
                else:
                    logger.error(f"Failed to setup posts headers: {response.get('error')}")
            except Exception as e:
                logger.exception(f"Error setting up posts headers: {e}")
        
        # Setup tokens sheet headers
        if self.tokens_sheet_id:
            try:
                headers = [
                    ["Timestamp", "Token Symbol", "Token Name", "Price", "24h Change %", "Volume 24h", "Market Cap",
                     "Trade Score", "Profit Prob %", "Risk Level", "Trading Signal", "Momentum", "Liquidity",
                     "Source", "AI Reasoning", "Notes"]
                ]
                
                response = self._execute_tool(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": self.tokens_sheet_id,
                        "sheet_name": "Token Tracking",
                        "values": headers,
                        "first_cell_location": "A1"
                    }
                )
                
                # Try old name if new name fails (backwards compatibility)
                if not response.get("successful") and "not found" in str(response.get('error', '')).lower():
                    response = self._execute_tool(
                        "GOOGLESHEETS_BATCH_UPDATE",
                        {
                            "spreadsheet_id": self.tokens_sheet_id,
                            "sheet_name": "AI Agent Memory",
                            "values": headers,
                            "first_cell_location": "A1"
                        }
                    )
                
                if response.get("successful"):
                    logger.info("✓ Tokens sheet headers set up")
                    results["tokens"] = True
                else:
                    logger.error(f"Failed to setup tokens headers: {response.get('error')}")
            except Exception as e:
                logger.exception(f"Error setting up tokens headers: {e}")
        
        return results
    
    def _rename_sheet_tab(self, spreadsheet_id: str, old_title: str, new_title: str) -> bool:
        """Rename a sheet tab (e.g., 'Sheet1' to 'AI Agent Memory').
        
        Args:
            spreadsheet_id: The spreadsheet ID
            old_title: Current sheet tab name
            new_title: New sheet tab name
            
        Returns:
            True if successful
        """
        try:
            # First, get the sheet ID (numeric gid) from the sheet name
            response = self._execute_tool(
                "GOOGLESHEETS_GET_SHEET_NAMES",
                {"spreadsheet_id": spreadsheet_id}
            )
            
            if not response.get("successful"):
                logger.error(f"Failed to get sheet names: {response.get('error')}")
                return False
            
            sheets = response.get("data", {}).get("sheets", [])
            sheet_id = None
            
            for sheet in sheets:
                # Handle both dict and string formats
                if isinstance(sheet, str):
                    # Sheet API returned just sheet names as strings
                    if sheet == old_title:
                        sheet_id = 0  # Use default sheet ID
                        break
                elif isinstance(sheet, dict):
                    properties = sheet.get("properties", {})
                    if properties.get("title") == old_title:
                        sheet_id = properties.get("sheetId")
                        break
            
            if sheet_id is None:
                logger.warning(f"Sheet '{old_title}' not found, trying with sheetId=0")
                sheet_id = 0  # Default first sheet
            
            # Rename the sheet using updateSheetProperties
            rename_response = self._execute_tool(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": spreadsheet_id,
                    "requests": [{
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "title": new_title
                            },
                            "fields": "title"
                        }
                    }]
                }
            )
            
            if rename_response.get("successful"):
                logger.info(f"✓ Renamed sheet tab from '{old_title}' to '{new_title}'")
                return True
            else:
                logger.error(f"Failed to rename sheet: {rename_response.get('error')}")
                return False
                
        except Exception as e:
            logger.exception(f"Error renaming sheet tab: {e}")
            return False
    
    @staticmethod
    def _is_cell_limit_error(error_msg: str) -> bool:
        """Check if error message indicates Google Sheets cell limit reached."""
        if not error_msg:
            return False
        error_lower = str(error_msg).lower()
        return (
            "10,000,000 cells" in error_msg or
            "10000000 cells" in error_msg or
            "exceeding google sheets' limit" in error_lower or
            "cannot expand sheet" in error_lower
        )
    
    def _create_new_tokens_sheet_and_update_env(self) -> str | None:
        """Create new tokens sheet when current one hits cell limit.
        
        Returns:
            New sheet ID if successful, None otherwise
        """
        try:
            # Create new sheet with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            new_title = f"FDWA AI Agent - Crypto Tokens - {timestamp}"
            
            logger.info(f"🆕 Creating new tokens sheet: {new_title}")
            new_sheet_id = self._create_sheet_with_fallback(new_title, "en_US")
            
            if not new_sheet_id:
                logger.error("Failed to create new tokens sheet")
                return None
            
            # Rename default "Sheet1" to "Token Tracking"
            self._rename_sheet_tab(new_sheet_id, "Sheet1", "Token Tracking")
            
            # Set up headers on new sheet
            self._setup_tokens_headers(new_sheet_id)
            
            # Update .env file
            _update_env_file("GOOGLESHEETS_TOKENS_SPREADSHEET_ID", new_sheet_id)
            
            # Update instance variable
            self.tokens_sheet_id = new_sheet_id
            
            # Update global variable
            global TOKENS_SHEET_ID
            TOKENS_SHEET_ID = new_sheet_id
            
            logger.info(f"✅ New tokens sheet created and configured: {new_sheet_id}")
            return new_sheet_id
            
        except Exception as e:
            logger.exception(f"Error creating new tokens sheet: {e}")
            return None
    
    def _create_new_posts_sheet_and_update_env(self) -> str | None:
        """Create new posts sheet when current one hits cell limit.
        
        Returns:
            New sheet ID if successful, None otherwise
        """
        try:
            # Create new sheet with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            new_title = f"FDWA AI Agent - Social Media Posts - {timestamp}"
            
            logger.info(f"🆕 Creating new posts sheet: {new_title}")
            new_sheet_id = self._create_sheet_with_fallback(new_title, "en_US")
            
            if not new_sheet_id:
                logger.error("Failed to create new posts sheet")
                return None
            
            # Rename default "Sheet1" to "Posts Tracking"
            self._rename_sheet_tab(new_sheet_id, "Sheet1", "Posts Tracking")
            
            # Set up headers on new sheet
            self._setup_posts_headers(new_sheet_id)
            
            # Update .env file
            _update_env_file("GOOGLESHEETS_POSTS_SPREADSHEET_ID", new_sheet_id)
            
            # Update instance variable
            self.posts_sheet_id = new_sheet_id
            
            # Update global variable
            global POSTS_SHEET_ID
            POSTS_SHEET_ID = new_sheet_id
            
            logger.info(f"✅ New posts sheet created and configured: {new_sheet_id}")
            return new_sheet_id
            
        except Exception as e:
            logger.exception(f"Error creating new posts sheet: {e}")
            return None
    
    @staticmethod
    def _get_content_hash(content: str) -> str:
        """Generate hash for content."""
        import hashlib
        normalized = re.sub(r'https?://\S+', '', content.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]


# Global instance
sheets_agent = GoogleSheetsAgent()


# Convenience functions for other agents to use
def save_post_to_sheets(platform: str, content: str, post_id: str = "",
                       image_url: str = "", metadata: Dict | None = None) -> bool:
    """Save social media post to Google Sheets."""
    return sheets_agent.save_post(platform, content, post_id, image_url, metadata)


def save_token_to_sheets(symbol: str, **kwargs) -> bool:
    """Save crypto token to Google Sheets."""
    return sheets_agent.save_crypto_token(symbol, **kwargs)


def save_tokens_to_sheets_batch(tokens: list[dict]) -> int:
    """Save multiple crypto tokens to Google Sheets in one API call."""
    return sheets_agent.save_crypto_tokens_batch(tokens)


def search_posts_in_sheets(platform: str | None = None, days_back: int = 30) -> List[Dict]:
    """Search posts from Google Sheets."""
    return sheets_agent.search_posts(platform, days_back)


def search_tokens_in_sheets(symbol: str | None = None, source: str | None = None) -> List[Dict]:
    """Search crypto tokens from Google Sheets."""
    return sheets_agent.search_tokens(symbol, source)


def setup_sheets_headers() -> Dict[str, bool]:
    """Set up headers in both Google Sheets (posts and tokens).
    
    Call this once when using new/blank spreadsheets.
    
    Returns:
        Dict with 'posts' and 'tokens' keys indicating success
    """
    return sheets_agent.setup_headers()


def extract_crypto_tokens_from_text(text: str) -> List[str]:
    """Extract potential crypto token symbols from text.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of potential token symbols
    """
    # Common crypto patterns
    patterns = [
        r'\$([A-Z]{2,10})\b',  # $BTC, $ETH format (capture group)
        r'\b([A-Z]{2,10})(?:USD|USDT)\b',  # BTCUSDT format (capture group)
    ]
    
    tokens = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Match is already cleaned due to capture group
            if 2 <= len(match) <= 10:
                tokens.add(match)
    
    return list(tokens)


def save_ai_analyzed_tokens(token_analyses: List, source: str = "ai_crypto_analyzer") -> int:
    """Save multiple AI-analyzed tokens to Google Sheets.
    
    Args:
        token_analyses: List of TokenAnalysis objects from CryptoTradingAnalyzer
        source: Data source identifier (default: ai_crypto_analyzer)
        
    Returns:
        Number of tokens successfully saved
    """
    saved_count = 0
    
    for token in token_analyses:
        try:
            success = sheets_agent.save_crypto_token(
                symbol=token.symbol,
                name=token.name,
                price=f"${token._format_price()}",
                percent_change_24h=f"{token.percent_change_24h:+.2f}%",
                volume_24h=f"${token.volume_24h:,.0f}",
                market_cap=f"${token.market_cap:,.0f}",
                trade_score=f"{token.trade_score:.0f}",
                profit_probability=f"{token.profit_probability:.0f}%",
                risk_level=token.risk_level,
                trading_signal=token.trading_signal,
                momentum=token.momentum,
                liquidity=token.liquidity,
                source=source,
                reasoning=token.reasoning,
                notes="AI-selected trading opportunity"
            )
            if success:
                saved_count += 1
        except Exception as e:
            logger.error(f"Failed to save token {token.symbol}: {e}")
    
    logger.info(f"✓ Saved {saved_count}/{len(token_analyses)} AI-analyzed tokens to Google Sheets")
    return saved_count

def initialize_google_sheets() -> Dict[str, str]:
    """Validate Google Sheets configuration.

    This function will NOT create spreadsheets. It only checks that
    `GOOGLESHEETS_POSTS_SPREADSHEET_ID` and `GOOGLESHEETS_TOKENS_SPREADSHEET_ID`
    are present in the environment and returns their values.

    Returns:
        Dict with 'posts_sheet_id' and 'tokens_sheet_id' (empty string if missing)
    """
    global POSTS_SHEET_ID, TOKENS_SHEET_ID
    result = {"posts_sheet_id": POSTS_SHEET_ID or "", "tokens_sheet_id": TOKENS_SHEET_ID or ""}

    if not POSTS_SHEET_ID:
        logger.warning("GOOGLESHEETS_POSTS_SPREADSHEET_ID not set in .env — Sheets saving will be disabled.")
    else:
        logger.info("Found GOOGLESHEETS_POSTS_SPREADSHEET_ID in environment")

    if not TOKENS_SHEET_ID:
        logger.warning("GOOGLESHEETS_TOKENS_SPREADSHEET_ID not set in .env — Token tracking will be disabled.")
    else:
        logger.info("Found GOOGLESHEETS_TOKENS_SPREADSHEET_ID in environment")

    return result


def _update_env_file(key: str, value: str):
    """Update .env file with a new key-value pair."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    
    try:
        # Read current .env
        with open(env_path, encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find and update or append
        key_found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                key_found = True
                break
        
        if not key_found:
            lines.append(f"\n{key}={value}\n")
        
        # Write back
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        logger.debug(f"Updated .env: {key}={value}")
    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")