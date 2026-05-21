"""
动量突破策略 — 基于 K线数据识别价格突破

核心逻辑:
1. 从热门代币榜获取候选池
2. 逐token获取K线, 计算近期价格区间
3. 识别突破: 当前价突破 N 周期高点 -> 做多信号
4. ATR止损止盈 + 成交量确认
"""

import numpy as np
from typing import Optional
from strategies.base import BaseStrategy, Signal
from data.fetcher import fetch_ohlc, fetch_trending


class MomentumBreakoutStrategy(BaseStrategy):
    """动量突破策略"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.lookback = config.get("lookback", 20)
        self.breakout_threshold = config.get("breakout_threshold", 0.03)
        self.volume_spike_mult = config.get("volume_spike_mult", 2.0)
        self.min_confidence = config.get("min_confidence", 0.55)
        self.chain = config.get("chain", "solana")

    def scan(self) -> list[Signal]:
        """扫描热门代币，检测动量突破"""
        signals = []
        try:
            trending = fetch_trending(self.chain, limit=10)
        except Exception as e:
            self.log(f"trending fetch failed: {e}")
            return signals

        for token in trending[:10]:
            addr = token.get("tokenContractAddress") or token.get("tokenAddress", "")
            symbol = token.get("tokenSymbol") or token.get("symbol", addr[:8])
            if not addr:
                continue

            sig = self._analyze_token(addr, symbol)
            if sig:
                signals.append(sig)

        return signals

    def analyze(self, token_address: str) -> Optional[dict]:
        """深度分析单个代币的动量状态"""
        sig = self._analyze_token(token_address, "")
        if sig is None:
            return {"status": "no_signal"}
        return {
            "token": sig.token_symbol,
            "direction": sig.direction,
            "confidence": sig.confidence,
            "entry_price": sig.entry_price,
            "stop_loss": sig.stop_loss,
            "take_profit": sig.take_profit,
            "reason": sig.reason,
        }

    def _analyze_token(self, addr: str, symbol: str) -> Optional[Signal]:
        """核心分析逻辑"""
        try:
            candles = fetch_ohlc(addr, self.chain, interval="15m", limit=100)
        except Exception:
            return None

        if not candles or len(candles) < self.lookback:
            return None

        # 提取 OHLC - 兼容多种字段名
        closes = []
        highs = []
        lows = []
        volumes = []
        for c in candles:
            closes.append(float(c.get("close") or c.get("c", 0)))
            highs.append(float(c.get("high") or c.get("h", 0)))
            lows.append(float(c.get("low") or c.get("l", 0)))
            volumes.append(float(c.get("volume") or c.get("v", 0)))

        closes = np.array(closes)
        highs = np.array(highs)
        lows = np.array(lows)
        volumes = np.array(volumes)

        if closes[-1] <= 0:
            return None

        current_price = closes[-1]
        lookback_high = np.max(highs[-self.lookback:-1]) if len(highs) >= self.lookback + 1 else np.max(highs)
        lookback_low = np.min(lows[-self.lookback:-1]) if len(lows) >= self.lookback + 1 else np.min(lows)
        avg_volume = np.mean(volumes[-self.lookback:-1]) if len(volumes) > self.lookback else np.mean(volumes)
        current_volume = volumes[-1]

        momentum_score = self._calc_momentum(closes, volumes)
        breakout_up = current_price > lookback_high * (1 + self.breakout_threshold / 2)
        volume_spike = current_volume > avg_volume * self.volume_spike_mult if avg_volume > 0 else False

        direction = None
        confidence = 0.0
        reason_parts = []

        if breakout_up and volume_spike:
            direction = "long"
            confidence = min(0.9, 0.5 + momentum_score * 0.4)
            reason_parts.append(f"Breakout above {self.lookback}-period high + volume spike")
        elif breakout_up:
            direction = "long"
            confidence = min(0.75, 0.35 + momentum_score * 0.4)
            reason_parts.append(f"Price breakout, low volume")
        else:
            return None

        if confidence < self.min_confidence:
            return None

        atr = self._calc_atr(highs, lows, closes, period=14)
        stop_loss = current_price * (1 - max(0.03, atr / current_price))
        take_profit = current_price * (1 + max(0.06, 2 * atr / current_price))

        if volume_spike:
            ratio = current_volume / max(avg_volume, 1)
            reason_parts.append(f"Volume {ratio:.1f}x")
        reason_parts.append(f"Momentum: {momentum_score:.2f}")

        return Signal(
            token_address=addr,
            token_symbol=symbol or addr[:8],
            chain=self.chain,
            direction=direction,
            confidence=round(confidence, 3),
            entry_price=float(current_price),
            stop_loss=round(float(stop_loss), 8),
            take_profit=round(float(take_profit), 8),
            reason="; ".join(reason_parts),
        )

    def _calc_momentum(self, closes: np.ndarray, volumes: np.ndarray) -> float:
        if len(closes) < 10:
            return 0.0
        short_roc = (closes[-1] - closes[-5]) / max(closes[-5], 1e-10)
        long_idx = min(20, len(closes))
        long_roc = (closes[-1] - closes[-long_idx]) / max(closes[-long_idx], 1e-10)
        vol_trend = volumes[-5:].mean() / max(volumes[-15:-5].mean(), 1e-10) if len(volumes) >= 15 else 1.0
        score = short_roc * 3.0 + long_roc * 0.5 + (vol_trend - 1.0) * 0.3
        return float(np.clip(score, -1.0, 1.0))

    @staticmethod
    def _calc_atr(highs, lows, closes, period=14):
        if len(closes) < 2:
            return 0.01
        prev_close = np.roll(closes, 1)
        prev_close[0] = closes[0]
        tr = np.maximum(highs - lows, np.abs(highs - prev_close))
        tr = np.maximum(tr, np.abs(lows - prev_close))
        atr = float(np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr))
        return atr
