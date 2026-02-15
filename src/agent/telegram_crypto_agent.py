"""
🚀 Telegram Crypto Agent - Token-Focused Messaging

This agent focuses SPECIFICALLY on crypto token data for Telegram posts.
- Uses CoinMarketCap API for real crypto token data (prices, market cap, volume)
- Sends ONLY token analysis and market insights to Telegram
- Saves detailed analysis to memory and Google Sheets  
- Formats content for @yieldbotai Telegram group

Architecture:
1. Data Source: CoinMarketCap API for live crypto token data
2. Analysis: CryptoTradingAnalyzer for token filtering and insights
3. Content: Token-focused messages only (no general business content)
4. Storage: Memory system + Google Sheets for full analysis data
5. Posting: Telegram group via Composio

Note: SERPAPI/Tavily are used by main blog agents for trend correlation, 
not by this crypto-specific agent.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio

# Add project root to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from composio import Composio
from src.agent.crypto_trading_analyzer import CryptoTradingAnalyzer
from src.agent.memory_store import AgentMemoryStore
from src.agent.cmc_client import get_top_by_market_cap

logger = logging.getLogger(__name__)

class TelegramCryptoAgent:
    """Focused crypto token agent for Telegram posts."""
    
    def __init__(self):
        """Initialize the Telegram crypto agent."""
        # Initialize Composio client for Telegram posting only
        self.composio_client = Composio(
            api_key=os.getenv("COMPOSIO_API_KEY"),
            entity_id=os.getenv("TELEGRAM_ENTITY_ID"),
            toolkit_versions={
                "telegram": "20260211_00"
            }
        )
        self.crypto_analyzer = CryptoTradingAnalyzer()
        self.memory_store = AgentMemoryStore(user_id="fdwa_agent")
        
        # Telegram configuration
        self.telegram_account_id = os.getenv("TELEGRAM_ACCOUNT_ID")
        self.telegram_group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")  # -1003331527610
        
        # CoinMarketCap API for crypto data (not SERPAPI/Tavily)
        self.coinmarketcap_api_key = os.getenv("COINMARKETCAP_API_KEY")
        
        logger.info("✅ TelegramCryptoAgent initialized")
        logger.info("   📱 Telegram Group: %s", self.telegram_group_chat_id)
        logger.info("   � CoinMarketCap: %s", "✓" if self.coinmarketcap_api_key else "✗")
        logger.info("   🎯 Focus: Token data via CryptoTradingAnalyzer")

    async def get_crypto_market_data(self) -> Dict[str, any]:
        """Get crypto market data using CoinMarketCap API.
        
        Fetches top tokens by market cap (avoiding pump & dumps),
        then identifies gainers/losers within quality tokens.
        
        Returns:
            Dict with market data and token information
        """
        logger.info("💰 Fetching quality crypto tokens from CoinMarketCap...")
        
        try:
            # Fetch top 200 tokens by market cap (quality tokens only)
            all_tokens = get_top_by_market_cap(limit=200)
            
            if not all_tokens:
                logger.warning("⚠️ No market data available")
                return self._get_fallback_crypto_data()
            
            logger.info("📥 Fetched %d quality tokens by market cap", len(all_tokens))
            
            # Separate into gainers and losers (from quality tokens)
            gainers = []
            losers = []
            
            for token in all_tokens:
                try:
                    pct_change = token.get('quote', {}).get('USD', {}).get('percent_change_24h', 0)
                    if pct_change > 0:
                        gainers.append(token)
                    elif pct_change < 0:
                        losers.append(token)
                except Exception:
                    continue
            
            # Sort gainers by percent change (descending)
            gainers.sort(key=lambda x: x.get('quote', {}).get('USD', {}).get('percent_change_24h', 0), reverse=True)
            # Sort losers by percent change (ascending - most negative first)
            losers.sort(key=lambda x: x.get('quote', {}).get('USD', {}).get('percent_change_24h', 0))
            
            # Take top 50 of each for analysis
            gainers = gainers[:50]
            losers = losers[:50]
            
            logger.info("📊 Filtered to %d gainers and %d losers from quality tokens", 
                       len(gainers), len(losers))
            
            # Analyze and filter with AI trading logic
            logger.info("🔍 Running AI trading analysis...")
            
            best_gainers, best_losers = CryptoTradingAnalyzer.analyze_tokens(
                gainers=gainers, 
                losers=losers, 
                top_n=5
            )
            
            selected_tokens = {
                "gainers": [
                    {
                        "symbol": token.symbol,
                        "name": token.name,
                        "price": token.price_usd,
                        "change_24h": token.percent_change_24h,
                        "market_cap": token.market_cap,
                        "volume_24h": token.volume_24h,
                        "trade_score": token.trade_score,
                        "profit_probability": token.profit_probability,
                        "risk_level": token.risk_level,
                        "signal": token.trading_signal,
                        "reasoning": token.reasoning
                    }
                    for token in best_gainers
                ],
                "losers": [
                    {
                        "symbol": token.symbol,
                        "name": token.name,
                        "price": token.price_usd,
                        "change_24h": token.percent_change_24h,
                        "market_cap": token.market_cap,
                        "volume_24h": token.volume_24h,
                        "trade_score": token.trade_score,
                        "profit_probability": token.profit_probability,
                        "risk_level": token.risk_level,
                        "signal": token.trading_signal,
                        "reasoning": token.reasoning
                    }
                    for token in best_losers
                ]
            }
            
            logger.info("✅ Selected %d best gainers and %d best losers", 
                       len(best_gainers), len(best_losers))
            
            return {
                "tokens": selected_tokens,
                "source": "CoinMarketCap",
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            }
                
        except Exception as e:
            logger.error("❌ CoinMarketCap API failed: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            return self._get_fallback_crypto_data()

    def _get_fallback_crypto_data(self) -> Dict[str, any]:
        """Generate fallback crypto content when API calls fail."""
        logger.info("🔄 Using fallback crypto data...")
        
        fallback_content = f"""🎯 Crypto Market Update - {datetime.now().strftime('%B %d, %Y')}

📈 Market Focus: Quality tokens with strong fundamentals  
💡 Key Metrics: Market cap >$1M, Volume >$100K daily
🔍 Data Source: CoinMarketCap API

📊 Remember: Always DYOR (Do Your Own Research)  
⚠️ Not financial advice - trade responsibly"""

        return {
            "tokens": [],
            "source": "Fallback", 
            "timestamp": datetime.utcnow().isoformat(),
            "fallback_message": fallback_content
        }

    async def analyze_and_filter_tokens(self) -> Tuple[List[Dict], Dict]:
        """Analyze crypto market and filter quality tokens.
        
        Returns:
            Tuple of (filtered_tokens, analysis_summary)
        """
        logger.info("🔄 Analyzing crypto market for quality tokens...")
        
        try:
            # Get market data and analyze
            analysis_result = await asyncio.to_thread(self.crypto_analyzer.analyze_and_select_tokens)
            
            if not analysis_result.get("success"):
                logger.warning("⚠️ Crypto analysis failed")
                return [], {"error": "Analysis failed"}
            
            # Extract quality tokens
            selected_tokens = analysis_result.get("selected_tokens", [])
            market_summary = analysis_result.get("market_summary", {})
            
            logger.info("✅ Found %d quality tokens", len(selected_tokens))
            
            # Save detailed analysis to memory
            if selected_tokens:
                await self._save_analysis_to_memory(selected_tokens, market_summary)
            
            return selected_tokens, market_summary
            
        except Exception as e:
            logger.error("❌ Token analysis failed: %s", e)
            return [], {"error": str(e)}

    async def _save_analysis_to_memory(self, tokens: List[Dict], summary: Dict):
        """Save detailed crypto analysis to memory and Google Sheets."""
        try:
            # Save to memory store
            for token in tokens:
                insight = f"{token['symbol']} - {token.get('analysis_reason', 'Selected for trading potential')}"
                await self.memory_store.record_crypto_insight(insight, {
                    "symbol": token.get("symbol"),
                    "price": token.get("price"),
                    "change_24h": token.get("percent_change_24h"),
                    "market_cap": token.get("market_cap"),
                    "volume_24h": token.get("volume_24h"),
                    "analysis_date": datetime.now().isoformat()
                })
            
            # Save summary to Google Sheets
            await self._save_to_sheets(tokens, summary)
            
            logger.info("✅ Analysis saved to memory and sheets")
            
        except Exception as e:
            logger.warning("⚠️ Failed to save analysis: %s", e)

    async def _save_to_sheets(self, tokens: List[Dict], summary: Dict):
        """Save token analysis to Google Sheets for tracking."""
        try:
            sheet_id = os.getenv("GOOGLESHEETS_TOKENS_SPREADSHEET_ID")
            if not sheet_id:
                logger.warning("⚠️ No Google Sheets ID configured")
                return
            
            # Prepare data for sheets
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            for token in tokens[:5]:  # Top 5 tokens only
                row_data = [
                    timestamp,
                    token.get("symbol", ""),
                    token.get("name", ""),
                    token.get("price", 0),
                    token.get("percent_change_24h", 0),
                    token.get("market_cap", 0),
                    token.get("volume_24h", 0),
                    token.get("analysis_reason", "AI selected"),
                    "Telegram"  # platform
                ]
                
                # Save to sheets
                self.composio_client.tools.execute(
                    "GOOGLESHEETS_BATCH_UPDATE",
                    {
                        "spreadsheet_id": sheet_id,
                        "values": [row_data],
                        "range": "Tokens!A:I"
                    },
                    connected_account_id=os.getenv("GOOGLESHEETS_ACCOUNT_ID")
                )
            
            logger.info("✅ Saved %d tokens to Google Sheets", len(tokens))
            
        except Exception as e:
            logger.warning("⚠️ Failed to save to sheets: %s", e)

    def create_telegram_message(self, trends: str, tokens: List[Dict], summary: Dict) -> str:
        """Create focused crypto message for Telegram.
        
        Args:
            trends: Trend research data
            tokens: Filtered quality tokens
            summary: Market analysis summary
            
        Returns:
            Telegram-optimized crypto message
        """
        logger.info("✍️ Creating Telegram crypto message...")
        
        message_parts = []
        
        # Header
        message_parts.append("🚀 DeFi Market Update")
        message_parts.append("")
        
        # Trending tokens (if any)
        if tokens and len(tokens) >= 2:
            top_tokens = tokens[:2]  # Top 2 tokens
            token_symbols = [t.get("symbol", "").upper() for t in top_tokens]
            message_parts.append(f"📊 Trending: {' | '.join(token_symbols)}")
            
            # Add brief analysis for top token
            top_token = tokens[0]
            change = top_token.get("percent_change_24h", 0)
            direction = "📈" if change > 0 else "📉"
            message_parts.append(f"{direction} {top_token.get('symbol', '')}: {change:.1f}% (24h)")
            
        elif trends:
            # Extract trending info from research
            trend_lines = trends.split('\n')[:2]
            for line in trend_lines:
                if line.strip() and len(line) > 10:
                    clean_line = line.replace("🎯", "📊").replace("📈", "").replace("💡", "")
                    message_parts.append(clean_line.strip()[:60])
        
        message_parts.append("")
        
        # Key insight from trends or analysis
        if "DeFi" in trends or "defi" in trends.lower():
            message_parts.append("📈 Create unique dispute letters with Letters by AI")
        elif tokens:
            message_parts.append("💡 AI-powered token analysis identifies market opportunities")
        else:
            message_parts.append("📈 Create unique dispute letters with Letters by AI")
        
        message_parts.append("")
        
        # Call to action
        message_parts.append("💡 Stay ahead with real-time DeFi insights and AI-powered automation.")
        message_parts.append("Get YBOT tools at https://fdwa.site")
        message_parts.append("")
        message_parts.append("#DeFi #Crypto #YieldBot #FinancialFreedom")
        
        message = "\n".join(message_parts)
        
        # Ensure message is under Telegram limit (4096 chars)
        if len(message) > 4000:
            message = message[:3950] + "...\n\n#DeFi #Crypto #YieldBot"
        
        logger.info("✅ Created Telegram message (%d chars)", len(message))
        return message

    async def send_telegram_message(self, message: str) -> bool:
        """Send crypto message to Telegram group.
        
        Args:
            message: Formatted crypto message
            
        Returns:
            Success status
        """
        try:
            logger.info("📱 Sending message to Telegram group...")
            
            result = self.composio_client.tools.execute(
                "TELEGRAM_SEND_MESSAGE",
                {
                    "chat_id": self.telegram_group_chat_id,
                    "text": message,
                    "parse_mode": "HTML"  # Enable HTML formatting
                },
                connected_account_id=self.telegram_account_id
            )
            
            if result.get("success", True):  # Assume success if no error
                logger.info("✅ Telegram message sent successfully")
                
                # Record success in memory
                await self.memory_store.record_post_performance(
                    "crypto_update", "telegram", True
                )
                
                return True
            else:
                logger.error("❌ Telegram send failed: %s", result.get("error"))
                return False
                
        except Exception as e:
            logger.error("❌ Failed to send Telegram message: %s", e)
            return False

    async def run_crypto_workflow(self) -> Dict[str, any]:
        """Run complete crypto-focused Telegram workflow.
        
        Returns:
            Workflow results and statistics
        """
        logger.info("🚀 Starting Telegram crypto workflow...")
        start_time = datetime.now()
        
        workflow_results = {
            "success": False,
            "timestamp": start_time.isoformat(),
            "components": {}
        }
        
        try:
            # Step 1: Research crypto trends
            logger.info("1️⃣ Researching crypto trends...")
            trend_result = await self.research_crypto_trends()
            trends = trend_result.get("trend_data", "")
            workflow_results["components"]["trends"] = {
                "success": bool(trends and len(trends) > 30),
                "source": trend_result.get("source"),
                "data_length": len(trends)
            }
            
            # Step 2: Analyze and filter tokens
            logger.info("2️⃣ Analyzing crypto tokens...")
            tokens, analysis_summary = await self.analyze_and_filter_tokens()
            workflow_results["components"]["analysis"] = {
                "success": len(tokens) > 0,
                "tokens_found": len(tokens),
                "analysis_summary": analysis_summary
            }
            
            # Step 3: Create telegram message  
            logger.info("3️⃣ Creating Telegram message...")
            message = self.create_telegram_message(trends, tokens, analysis_summary)
            workflow_results["components"]["content"] = {
                "success": len(message) > 100,
                "message_length": len(message)
            }
            
            # Step 4: Send to Telegram
            logger.info("4️⃣ Sending to Telegram...")
            send_success = await self.send_telegram_message(message)
            workflow_results["components"]["telegram"] = {
                "success": send_success,
                "message": message if send_success else None
            }
            
            # Overall success
            workflow_results["success"] = all(
                component.get("success", False) 
                for component in workflow_results["components"].values()
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            workflow_results["duration_seconds"] = duration
            
            logger.info("✅ Crypto workflow completed in %.1fs", duration)
            logger.info("📊 Success rate: %d/4 components", 
                       sum(1 for c in workflow_results["components"].values() if c.get("success")))
            
            return workflow_results
            
        except Exception as e:
            logger.error("❌ Crypto workflow failed: %s", e)
            workflow_results["error"] = str(e)
            workflow_results["success"] = False
            return workflow_results


# ============================================================================
# CLI Interface for Testing
# ============================================================================

async def main():
    """Test the Telegram crypto agent."""
    print("🚀 Testing Telegram Crypto Agent...")
    
    agent = TelegramCryptoAgent()
    results = await agent.run_crypto_workflow()
    
    print("\n📊 WORKFLOW RESULTS:")
    print("=" * 50)
    print(f"✅ Success: {results['success']}")
    print(f"⏱️  Duration: {results.get('duration_seconds', 0):.1f}s")
    print()
    
    for component, data in results.get("components", {}).items():
        status = "✅" if data.get("success") else "❌"
        print(f"{status} {component.title()}: {data}")
    
    if results.get("components", {}).get("telegram", {}).get("message"):
        print(f"\n📱 TELEGRAM MESSAGE:")
        print("-" * 30)
        print(results["components"]["telegram"]["message"])

if __name__ == "__main__":
    asyncio.run(main())