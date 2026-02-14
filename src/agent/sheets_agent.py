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
from typing import Dict, List, Optional, Any

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
        self.account_id = os.getenv("GOOGLESHEETS_ACCOUNT_ID")
        self.posts_sheet_id = POSTS_SHEET_ID
        self.tokens_sheet_id = TOKENS_SHEET_ID
        # cache discovered tool slugs to avoid repeated API calls
        self._discovered_create_slug: Optional[str] = None
        
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

    def _discover_sheets_create_tool(self) -> Optional[str]:
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
    def _create_sheet_with_fallback(self, title: str, locale: str = "en_US") -> Optional[str]:
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

                # If the discovered slug requires a toolkit version, use env or default
                toolkit_version = None
                env_key = f"COMPOSIO_TOOLKIT_VERSION_{slug}"
                if os.getenv(env_key):
                    toolkit_version = os.getenv(env_key)
                elif slug == "GOOGLESHEETS_CREATE_GOOGLE_SHEET1":
                    # default to the version observed in your Playground
                    toolkit_version = "20260211_00"

                resp = self._execute_tool(slug, {"title": title, "locale": locale}, toolkit_version=toolkit_version)

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

    def create_posts_spreadsheet(self) -> Optional[str]:
        """Create a new spreadsheet for tracking social media posts (fallback-aware)."""
        try:
            logger.info("Creating Social Media Posts tracking spreadsheet (fallback-aware)...")
            sheet_id = self._create_sheet_with_fallback("FDWA AI Agent - Social Media Posts", "en_US")

            if sheet_id:
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
    
    def create_tokens_spreadsheet(self) -> Optional[str]:
        """Create a new spreadsheet for tracking crypto tokens (fallback-aware)."""
        try:
            logger.info("Creating Crypto Tokens tracking spreadsheet (fallback-aware)...")
            sheet_id = self._create_sheet_with_fallback("FDWA AI Agent - Crypto Tokens", "en_US")

            if sheet_id:
                # Set up headers
                self._setup_tokens_headers(sheet_id)
                return sheet_id

            logger.error("Failed to create tokens spreadsheet with available tool slugs")
            return None

        except Exception as e:
            logger.exception(f"Error creating tokens spreadsheet: {e}")
            return None
    
    def _setup_tokens_headers(self, sheet_id: str):
        """Set up column headers for tokens sheet."""
        headers = [
            ["Timestamp", "Token Symbol", "Token Name", "Contract Address", "Chain",
             "Source", "Price", "Market Cap", "Mentions", "Sentiment", "Notes"]
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
                                "endColumnIndex": 11
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
                  image_url: str = "", metadata: Optional[Dict] = None) -> bool:
        """Save a social media post to Google Sheets.
        
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
            
            # Append to sheet using batch_update (omit first_cell_location to append)
            response = self._execute_tool(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": self.posts_sheet_id,
                    "sheet_name": "AI Agent Memory",
                    "values": [row_data]
                }
            )
            
            if response.get("successful"):
                logger.info(f"✓ Saved {platform} post to Google Sheets")
                return True
            else:
                logger.error(f"Failed to save post: {response.get('error')}")
                return False
                
        except Exception as e:
            logger.exception(f"Error saving post to Sheets: {e}")
            return False
    
    def save_crypto_token(self, symbol: str, name: str = "", contract: str = "",
                         chain: str = "ETH", source: str = "telegram",
                         price: str = "", market_cap: str = "", 
                         mentions: int = 1, sentiment: str = "neutral",
                         notes: str = "") -> bool:
        """Save a crypto token mention to Google Sheets.
        
        Args:
            symbol: Token symbol (e.g., BTC, ETH, DOGE)
            name: Full token name
            contract: Contract address
            chain: Blockchain (ETH, BSC, SOL, etc.)
            source: Where token was mentioned (telegram, twitter, etc.)
            price: Current price
            market_cap: Market cap
            mentions: Number of mentions
            sentiment: bullish, bearish, neutral
            notes: Additional notes
            
        Returns:
            True if saved successfully
        """
        if not self.tokens_sheet_id:
            logger.warning("Tokens spreadsheet not configured, skipping Sheets save")
            return False
        
        try:
            timestamp = datetime.now().isoformat()
            
            row_data = [
                timestamp,
                symbol.upper(),
                name,
                contract,
                chain.upper(),
                source,
                price,
                market_cap,
                str(mentions),
                sentiment,
                notes
            ]
            
            # Append to sheet using batch_update (omit first_cell_location to append)
            response = self._execute_tool(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": self.tokens_sheet_id,
                    "sheet_name": "AI Agent Memory",
                    "values": [row_data]
                }
            )
            
            if response.get("successful"):
                logger.info(f"✓ Saved {symbol} token to Google Sheets")
                return True
            else:
                logger.error(f"Failed to save token: {response.get('error')}")
                return False
                
        except Exception as e:
            logger.exception(f"Error saving token to Sheets: {e}")
            return False
    
    def search_posts(self, platform: Optional[str] = None, 
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
            response = self._execute_tool(
                "GOOGLESHEETS_BATCH_GET",
                {
                    "spreadsheet_id": self.posts_sheet_id,
                    "ranges": ["AI Agent Memory!A2:I1000"]  # Skip header, read up to 1000 rows
                }
            )
            
            if not response.get("successful"):
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
    
    def search_tokens(self, symbol: Optional[str] = None, 
                     source: Optional[str] = None, limit: int = 100) -> List[Dict]:
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
            response = self._execute_tool(
                "GOOGLESHEETS_BATCH_GET",
                {
                    "spreadsheet_id": self.tokens_sheet_id,
                    "ranges": ["AI Agent Memory!A2:K1000"]  # Skip header
                }
            )
            
            if not response.get("successful"):
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
                    "contract": row[3] if len(row) > 3 else "",
                    "chain": row[4] if len(row) > 4 else "",
                    "source": row[5] if len(row) > 5 else "",
                    "price": row[6] if len(row) > 6 else "",
                    "market_cap": row[7] if len(row) > 7 else "",
                    "mentions": row[8] if len(row) > 8 else "1",
                    "sentiment": row[9] if len(row) > 9 else "",
                    "notes": row[10] if len(row) > 10 else ""
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
                    ["Timestamp", "Symbol", "Name", "Contract", "Chain", "Source", 
                     "Price", "Market Cap", "Mentions", "Sentiment", "Notes"]
                ]
                
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
                       image_url: str = "", metadata: Optional[Dict] = None) -> bool:
    """Save social media post to Google Sheets."""
    return sheets_agent.save_post(platform, content, post_id, image_url, metadata)


def save_token_to_sheets(symbol: str, **kwargs) -> bool:
    """Save crypto token to Google Sheets."""
    return sheets_agent.save_crypto_token(symbol, **kwargs)


def search_posts_in_sheets(platform: Optional[str] = None, days_back: int = 30) -> List[Dict]:
    """Search posts from Google Sheets."""
    return sheets_agent.search_posts(platform, days_back)


def search_tokens_in_sheets(symbol: Optional[str] = None, source: Optional[str] = None) -> List[Dict]:
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
        with open(env_path, 'r', encoding='utf-8') as f:
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