"""AI-Powered Crypto Trading Analyzer for Telegram Posts

This module analyzes crypto tokens like a professional day trader would:
- Filters out low-quality/low-volume tokens (pump & dumps)
- Scores profit/loss probability based on multiple factors
- Identifies high-conviction trading opportunities
- Analyzes momentum, liquidity, and risk/reward ratios

Uses CoinMarketCap API + AI analysis to select the BEST tokens to show.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TokenAnalysis:
    """Trading analysis for a single token."""
    symbol: str
    name: str
    price_usd: float
    percent_change_24h: float
    volume_24h: float
    market_cap: float
    
    # Trading metrics
    trade_score: float  # 0-100: Overall trading opportunity score
    profit_probability: float  # 0-100: Estimated probability of profit
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    momentum: str  # "STRONG_UP", "MODERATE_UP", "WEAK", "MODERATE_DOWN", "STRONG_DOWN"
    liquidity: str  # "EXCELLENT", "GOOD", "FAIR", "POOR"
    
    # Trading insights
    trading_signal: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    reasoning: str  # Why this token was selected
    
    def __str__(self) -> str:
        """Format for Telegram display."""
        return (
            f"${self.symbol}: ${self._format_price()} ({self._format_pct()})\n"
            f"   📊 Score: {self.trade_score:.0f}/100 | 🎯 Profit Prob: {self.profit_probability:.0f}%\n"
            f"   ⚠️ Risk: {self.risk_level} | 🔥 {self.momentum}"
        )
    
    def _format_price(self) -> str:
        """Format price based on magnitude."""
        if self.price_usd >= 1:
            return f"{self.price_usd:,.2f}"
        elif self.price_usd >= 0.01:
            return f"{self.price_usd:.4f}"
        else:
            return f"{self.price_usd:.8f}"
    
    def _format_pct(self) -> str:
        """Format percentage with + or -."""
        return f"+{self.percent_change_24h:.2f}%" if self.percent_change_24h >= 0 else f"{self.percent_change_24h:.2f}%"


class CryptoTradingAnalyzer:
    """AI-powered analyzer that selects best trading opportunities."""
    
    # Trading thresholds (inspired by professional day traders)
    MIN_MARKET_CAP = 1_000_000  # $1M - filter out micro-cap pump & dumps
    MIN_VOLUME_24H = 100_000  # $100K - must have daily liquidity
    MIN_VOLUME_TO_MCAP_RATIO = 0.01  # 1% - volume should be proportional to mcap
    
    # Score weights (total = 100)
    WEIGHT_MOMENTUM = 30  # Price action strength
    WEIGHT_LIQUIDITY = 25  # Volume/market cap
    WEIGHT_VOLATILITY = 20  # Movement size (risk/reward)
    WEIGHT_MARKET_CAP = 15  # Size/stability
    WEIGHT_CONSISTENCY = 10  # Sustained vs sudden spike
    
    @staticmethod
    def analyze_tokens(
        gainers: List[Dict],
        losers: List[Dict],
        top_n: int = 5
    ) -> tuple[List[TokenAnalysis], List[TokenAnalysis]]:
        """Analyze and select the BEST trading opportunities from raw token data.
        
        Args:
            gainers: Raw token data from CoinMarketCap (top gainers)
            losers: Raw token data from CoinMarketCap (top losers)
            top_n: Number of best tokens to return for each category
            
        Returns:
            Tuple of (best_gainers, best_losers) with trading analysis
        """
        logger.info(f"🔍 Analyzing {len(gainers)} gainers and {len(losers)} losers...")
        
        # Analyze all tokens
        analyzed_gainers = [
            CryptoTradingAnalyzer._analyze_single_token(token, is_gainer=True)
            for token in gainers
        ]
        analyzed_losers = [
            CryptoTradingAnalyzer._analyze_single_token(token, is_gainer=False)
            for token in losers
        ]
        
        # Filter out None (tokens that failed quality checks)
        analyzed_gainers = [t for t in analyzed_gainers if t is not None]
        analyzed_losers = [t for t in analyzed_losers if t is not None]
        
        # Sort by trade_score (descending)
        analyzed_gainers.sort(key=lambda t: t.trade_score, reverse=True)
        analyzed_losers.sort(key=lambda t: t.trade_score, reverse=True)
        
        # Select top N
        best_gainers = analyzed_gainers[:top_n]
        best_losers = analyzed_losers[:top_n]
        
        logger.info(f"✅ Selected {len(best_gainers)} best gainers and {len(best_losers)} best losers")
        return best_gainers, best_losers
    
    @staticmethod
    def _analyze_single_token(token_data: Dict, is_gainer: bool) -> Optional[TokenAnalysis]:
        """Analyze a single token and assign trading scores.
        
        Returns None if token fails quality checks (pump & dump, low liquidity, etc.)
        """
        try:
            # Extract data
            symbol = token_data.get('symbol', '?')
            name = token_data.get('name', 'Unknown')
            quote = token_data.get('quote', {}).get('USD', {})
            
            price = quote.get('price')
            pct_change = quote.get('percent_change_24h')
            volume_24h = quote.get('volume_24h', 0)
            market_cap = quote.get('market_cap', 0)
            
            # Quality checks - filter out bad tokens
            if not price or not pct_change:
                return None
            
            if market_cap < CryptoTradingAnalyzer.MIN_MARKET_CAP:
                logger.debug(f"❌ {symbol}: Market cap too low (${market_cap:,.0f})")
                return None
            
            if volume_24h < CryptoTradingAnalyzer.MIN_VOLUME_24H:
                logger.debug(f"❌ {symbol}: Volume too low (${volume_24h:,.0f})")
                return None
            
            # Calculate trading metrics
            momentum_score = CryptoTradingAnalyzer._calculate_momentum(pct_change, is_gainer)
            liquidity_score = CryptoTradingAnalyzer._calculate_liquidity(volume_24h, market_cap)
            volatility_score = CryptoTradingAnalyzer._calculate_volatility(pct_change)
            mcap_score = CryptoTradingAnalyzer._calculate_mcap_score(market_cap)
            
            # Overall trade score (weighted average)
            trade_score = (
                momentum_score * CryptoTradingAnalyzer.WEIGHT_MOMENTUM / 100 +
                liquidity_score * CryptoTradingAnalyzer.WEIGHT_LIQUIDITY / 100 +
                volatility_score * CryptoTradingAnalyzer.WEIGHT_VOLATILITY / 100 +
                mcap_score * CryptoTradingAnalyzer.WEIGHT_MARKET_CAP / 100
            )
            
            # Profit probability (0-100%)
            profit_prob = CryptoTradingAnalyzer._calculate_profit_probability(
                trade_score, pct_change, volume_24h, market_cap, is_gainer
            )
            
            # Risk level
            risk_level = CryptoTradingAnalyzer._assess_risk(market_cap, volume_24h, pct_change)
            
            # Momentum label
            momentum = CryptoTradingAnalyzer._momentum_label(pct_change, is_gainer)
            
            # Liquidity label
            liquidity = CryptoTradingAnalyzer._liquidity_label(volume_24h, market_cap)
            
            # Trading signal
            trading_signal = CryptoTradingAnalyzer._generate_signal(trade_score, profit_prob, risk_level, is_gainer)
            
            # Reasoning
            reasoning = CryptoTradingAnalyzer._generate_reasoning(
                symbol, trade_score, profit_prob, volume_24h, market_cap, pct_change, is_gainer
            )
            
            return TokenAnalysis(
                symbol=symbol,
                name=name,
                price_usd=price,
                percent_change_24h=pct_change,
                volume_24h=volume_24h,
                market_cap=market_cap,
                trade_score=trade_score,
                profit_probability=profit_prob,
                risk_level=risk_level,
                momentum=momentum,
                liquidity=liquidity,
                trading_signal=trading_signal,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.warning(f"Failed to analyze token: {e}")
            return None
    
    @staticmethod
    def _calculate_momentum(pct_change: float, is_gainer: bool) -> float:
        """Score 0-100 based on price momentum strength."""
        abs_change = abs(pct_change)
        
        if abs_change >= 50:
            return 100  # Extreme momentum
        elif abs_change >= 20:
            return 80  # Strong momentum
        elif abs_change >= 10:
            return 60  # Moderate momentum
        elif abs_change >= 5:
            return 40  # Weak momentum
        else:
            return 20  # Very weak
    
    @staticmethod
    def _calculate_liquidity(volume_24h: float, market_cap: float) -> float:
        """Score 0-100 based on volume/market cap ratio."""
        if market_cap == 0:
            return 0
        
        ratio = volume_24h / market_cap
        
        if ratio >= 0.5:  # 50%+ daily turnover
            return 100
        elif ratio >= 0.2:  # 20%+ turnover
            return 80
        elif ratio >= 0.1:  # 10%+ turnover
            return 60
        elif ratio >= 0.05:  # 5%+ turnover
            return 40
        elif ratio >= 0.01:  # 1%+ turnover (minimum acceptable)
            return 20
        else:
            return 0
    
    @staticmethod
    def _calculate_volatility(pct_change: float) -> float:
        """Score 0-100 based on volatility (higher = more opportunity)."""
        abs_change = abs(pct_change)
        
        # Day traders love volatility (risk = reward)
        if abs_change >= 30:
            return 100
        elif abs_change >= 15:
            return 80
        elif abs_change >= 8:
            return 60
        elif abs_change >= 4:
            return 40
        else:
            return 20
    
    @staticmethod
    def _calculate_mcap_score(market_cap: float) -> float:
        """Score 0-100 based on market cap (stability vs opportunity)."""
        if market_cap >= 1_000_000_000:  # $1B+ (large cap)
            return 80  # Stable, lower risk
        elif market_cap >= 100_000_000:  # $100M+ (mid cap)
            return 90  # Sweet spot for day trading
        elif market_cap >= 10_000_000:  # $10M+ (small cap)
            return 70  # Higher risk, higher reward
        elif market_cap >= 1_000_000:  # $1M+ (micro cap)
            return 40  # Very risky
        else:
            return 0  # Too risky
    
    @staticmethod
    def _calculate_profit_probability(
        trade_score: float,
        pct_change: float,
        volume_24h: float,
        market_cap: float,
        is_gainer: bool
    ) -> float:
        """Estimate probability of profit (0-100%) based on multiple factors."""
        # Base probability from trade score
        base_prob = trade_score * 0.6  # 60% weight on overall score
        
        # Adjust for momentum sustainability
        abs_change = abs(pct_change)
        if abs_change > 100:
            momentum_factor = -10  # Likely exhausted (contrarian)
        elif abs_change > 50:
            momentum_factor = -5  # Overextended
        elif abs_change > 20:
            momentum_factor = 5  # Strong but sustainable
        elif abs_change > 10:
            momentum_factor = 10  # Sweet spot
        else:
            momentum_factor = 0  # Weak
        
        # Adjust for liquidity (can you actually trade it?)
        volume_to_mcap = volume_24h / market_cap if market_cap > 0 else 0
        if volume_to_mcap > 0.3:
            liquidity_factor = 15  # Excellent liquidity
        elif volume_to_mcap > 0.1:
            liquidity_factor = 10  # Good liquidity
        elif volume_to_mcap > 0.05:
            liquidity_factor = 5  # Fair liquidity
        else:
            liquidity_factor = -5  # Poor liquidity (hard to exit)
        
        # Combine
        profit_prob = base_prob + momentum_factor + liquidity_factor
        
        # Clamp to 0-100
        return max(0, min(100, profit_prob))
    
    @staticmethod
    def _assess_risk(market_cap: float, volume_24h: float, pct_change: float) -> str:
        """Determine risk level: LOW, MEDIUM, HIGH."""
        risk_score = 0
        
        # Market cap (smaller = riskier)
        if market_cap < 10_000_000:
            risk_score += 3
        elif market_cap < 100_000_000:
            risk_score += 2
        else:
            risk_score += 1
        
        # Liquidity (lower = riskier)
        volume_ratio = volume_24h / market_cap if market_cap > 0 else 0
        if volume_ratio < 0.05:
            risk_score += 3
        elif volume_ratio < 0.1:
            risk_score += 2
        else:
            risk_score += 1
        
        # Volatility (higher = riskier)
        abs_change = abs(pct_change)
        if abs_change > 50:
            risk_score += 3
        elif abs_change > 20:
            risk_score += 2
        else:
            risk_score += 1
        
        # Total risk (3-9 scale)
        if risk_score >= 7:
            return "HIGH"
        elif risk_score >= 5:
            return "MEDIUM"
        else:
            return "LOW"
    
    @staticmethod
    def _momentum_label(pct_change: float, is_gainer: bool) -> str:
        """Label momentum strength."""
        abs_change = abs(pct_change)
        
        if abs_change > 30:
            return "EXTREME" if is_gainer else "FALLING_KNIFE"
        elif abs_change > 15:
            return "STRONG" if is_gainer else "HEAVY_SELL"
        elif abs_change > 8:
            return "MODERATE" if is_gainer else "SELLING"
        else:
            return "WEAK" if is_gainer else "DRIFTING"
    
    @staticmethod
    def _liquidity_label(volume_24h: float, market_cap: float) -> str:
        """Label liquidity quality."""
        ratio = volume_24h / market_cap if market_cap > 0 else 0
        
        if ratio >= 0.3:
            return "EXCELLENT"
        elif ratio >= 0.1:
            return "GOOD"
        elif ratio >= 0.05:
            return "FAIR"
        else:
            return "POOR"
    
    @staticmethod
    def _generate_signal(trade_score: float, profit_prob: float, risk_level: str, is_gainer: bool) -> str:
        """Generate trading signal based on analysis."""
        if is_gainer:
            if trade_score >= 80 and profit_prob >= 70 and risk_level != "HIGH":
                return "STRONG_BUY"
            elif trade_score >= 65 and profit_prob >= 55:
                return "BUY"
            elif trade_score >= 50:
                return "HOLD"
            else:
                return "AVOID"
        else:
            # For losers, we're looking at shorting opportunities or bounce plays
            if trade_score >= 80 and profit_prob >= 70 and risk_level != "HIGH":
                return "BOUNCE_PLAY"  # High probability of reversal
            elif trade_score >= 65:
                return "SHORT_OPP"  # Good shorting opportunity
            elif trade_score >= 50:
                return "WATCH"
            else:
                return "AVOID"
    
    @staticmethod
    def _generate_reasoning(
        symbol: str,
        trade_score: float,
        profit_prob: float,
        volume_24h: float,
        market_cap: float,
        pct_change: float,
        is_gainer: bool
    ) -> str:
        """Generate human-readable reasoning for token selection."""
        reasons = []
        
        # Score reason
        if trade_score >= 80:
            reasons.append("exceptional opportunity")
        elif trade_score >= 65:
            reasons.append("strong setup")
        else:
            reasons.append("moderate potential")
        
        # Liquidity reason
        vol_ratio = volume_24h / market_cap if market_cap > 0 else 0
        if vol_ratio >= 0.2:
            reasons.append("highly liquid")
        elif vol_ratio >= 0.1:
            reasons.append("good liquidity")
        
        # Momentum reason
        abs_change = abs(pct_change)
        if abs_change > 50:
            reasons.append("extreme volatility" if is_gainer else "oversold potential")
        elif abs_change > 20:
            reasons.append("strong momentum" if is_gainer else "heavy selling")
        
        return f"{symbol}: " + ", ".join(reasons)
