"""
鲸鱼追踪策略 — 监控聪明钱/大户行为，跟随聪明钱流向

核心逻辑:
1. 从 onchainos signal list 获取聪明钱实时动态
2. signal 返回的是 token 维度的聚合数据:
   - triggerWalletCount: 同时触发该代币的聪明钱地址数
   - triggerWalletAddress: 逗号分隔的地址列表
   - walletType: 1=Smart Money, 2=KOL, 3=Whales
3. 当多个聪明钱地址同时买入时生成跟单信号
"""

from collections import defaultdict
from typing import Optional
from strategies.base import BaseStrategy, Signal
from data.fetcher import fetch_signals, fetch_top_traders, fetch_token_info, fetch_leaderboard


class WhaleTrackingStrategy(BaseStrategy):
    """鲸鱼追踪策略"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.chain = config.get("chain", "solana")
        self.min_whale_count = config.get("min_whale_count", 2)
        self.min_confidence = config.get("min_confidence", 0.5)

    def scan(self) -> list[Signal]:
        """扫描聪明钱信号"""
        signals = []

        try:
            raw = fetch_signals(self.chain, limit=30)
        except Exception as e:
            self.log(f"signal fetch failed: {e}")
            return signals

        items = raw if isinstance(raw, list) else raw.get("data", [])

        for item in items:
            # onchainos signal 格式: token.*, triggerWalletCount, walletType
            token_data = item.get("token", item)
            addr = token_data.get("tokenAddress") or item.get("tokenAddress", "")
            symbol = token_data.get("symbol") or item.get("symbol", addr[:8])

            if not addr:
                continue

            whale_count = int(item.get("triggerWalletCount", 1))
            if whale_count < self.min_whale_count:
                continue

            amount_usd = float(item.get("amountUsd", 0))
            price = float(item.get("price", 0))
            wallet_type = int(item.get("walletType", 1))

            confidence = min(0.95, 0.4 + whale_count * 0.12)
            type_label = {1: "SmartMoney", 2: "KOL", 3: "Whale"}.get(wallet_type, "Unknown")
            reason = f"{whale_count} {type_label} wallets buying, total ${amount_usd:,.0f}"

            signals.append(Signal(
                token_address=addr,
                token_symbol=symbol,
                chain=self.chain,
                direction="long",
                confidence=confidence,
                entry_price=price if price > 0 else 0.0001,
                stop_loss=round(price * 0.85, 8) if price > 0 else 0,
                take_profit=round(price * 1.35, 8) if price > 0 else 0,
                reason=reason,
            ))

        return signals

    def analyze(self, token_address: str) -> Optional[dict]:
        """深度分析某个代币的鲸鱼活动"""
        try:
            top_data = fetch_top_traders(token_address, self.chain, limit=20)
            info_data = fetch_token_info(token_address, self.chain)
            lb_data = fetch_leaderboard(self.chain, sort_by="1", time_frame="1", limit=10)
        except Exception as e:
            return {"error": str(e)}

        traders = top_data if isinstance(top_data, list) else top_data.get("data", [])
        whale_buys = [t for t in traders if str(t.get("side", "")).lower() == "buy"]
        whale_sells = [t for t in traders if str(t.get("side", "")).lower() == "sell"]

        return {
            "token": token_address,
            "whale_buy_count": len(whale_buys),
            "whale_sell_count": len(whale_sells),
            "net_whale_flow": len(whale_buys) - len(whale_sells),
            "top_buyers": whale_buys[:5],
            "top_sellers": whale_sells[:5],
            "token_info": info_data,
            "leaderboard": lb_data,
        }
