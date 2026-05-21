"""
新币狙击策略 — 扫描新创建的 meme/token，识别早期机会

核心逻辑:
1. 从 onchainos token hot-tokens 获取候选池 (按创建时间排序)
2. 过滤: 持有人数/流动性/捆绑比例/开发者记录
3. 风险评分: 捆绑% + 狙击手% + dev rug率 + 新钱包%
4. 生成狙击信号
"""

from typing import Optional
from datetime import datetime
from strategies.base import BaseStrategy, Signal
from data.fetcher import fetch_new_tokens, fetch_token_advanced, fetch_token_info


class NewTokenSnipeStrategy(BaseStrategy):
    """新币狙击策略"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.chain = config.get("chain", "solana")
        self.max_bundle_pct = config.get("max_bundle_pct", 30.0)
        self.min_liquidity = config.get("min_liquidity", 5000.0)
        self.min_holder_count = config.get("min_holder_count", 30)
        self.max_dev_rug_rate = config.get("max_dev_rug_rate", 0.3)
        self._scanned: set[str] = set()

    def scan(self) -> list[Signal]:
        """扫描新币"""
        signals = []

        try:
            tokens = fetch_new_tokens(self.chain, limit=30)
        except Exception as e:
            self.log(f"new token scan failed: {e}")
            return signals

        for token in tokens[:15]:
            addr = token.get("tokenContractAddress") or token.get("tokenAddress", "")
            if not addr or addr in self._scanned:
                continue
            self._scanned.add(addr)

            sig = self._evaluate_token(addr, token)
            if sig:
                signals.append(sig)

        return signals

    def analyze(self, token_address: str) -> Optional[dict]:
        """深度分析新币风险"""
        try:
            adv = fetch_token_advanced(token_address, self.chain)
            info = fetch_token_info(token_address, self.chain)
        except Exception as e:
            return {"error": str(e)}

        risk_score, risk_factors = self._calc_risk_score(adv, info)

        # 确定评级
        if risk_score < 40:
            verdict = "[SAFE] Snipeable"
        elif risk_score < 65:
            verdict = "[CAUTION] Monitor"
        else:
            verdict = "[DANGER] High risk"

        return {
            "token": token_address,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "advanced_info": adv,
            "token_info": info,
            "verdict": verdict,
        }

    def _safe_float(self, val, default=0.0):
        try:
            return float(val) if val != '' and val is not None else default
        except (ValueError, TypeError):
            return default

    def _evaluate_token(self, addr: str, raw: dict) -> Optional[Signal]:
        """快速评估新币"""
        symbol = raw.get("tokenSymbol") or raw.get("symbol", addr[:8])
        price = self._safe_float(raw.get("price", 0))
        volume = self._safe_float(raw.get("volume", 0))
        holders = int(self._safe_float(raw.get("holders", 0)))
        liquidity = self._safe_float(raw.get("liquidity", 0))
        bundle_pct = self._safe_float(raw.get("bundleHoldPercent", 0))

        # 基础过滤
        if liquidity < self.min_liquidity:
            return None
        if holders < self.min_holder_count:
            return None
        if bundle_pct > self.max_bundle_pct:
            return None

        # 获取高级信息做进一步风控
        try:
            adv = fetch_token_advanced(addr, self.chain)
        except Exception:
            adv = {}

        risk_score, risk_factors = self._calc_risk_score(adv, raw)
        if risk_score > 65:
            return None

        entry_price = price if price > 0 else 0.0001
        confidence = max(0.30, min(0.85, (100 - risk_score) / 100))

        # 价格变化过滤
        change = self._safe_float(raw.get("change", 0))
        if change < -20:
            confidence *= 0.5

        return Signal(
            token_address=addr,
            token_symbol=symbol,
            chain=self.chain,
            direction="long",
            confidence=round(confidence, 3),
            entry_price=entry_price,
            stop_loss=round(entry_price * 0.78, 8),
            take_profit=round(entry_price * 2.5, 8),
            reason="; ".join(risk_factors[:3]) if risk_factors else "New token snipe signal",
        )

    def _calc_risk_score(self, adv: dict, token_data: dict) -> tuple[float, list[str]]:
        """计算风险评分 0-100 (越低越安全)"""
        risk = 0.0
        factors = []

        # 捆绑比例
        bundle_pct = float(adv.get("bundleHoldPercent") or token_data.get("bundleHoldPercent", 0))
        if bundle_pct > self.max_bundle_pct:
            risk += 30
            factors.append(f"High bundle: {bundle_pct:.0f}%")
        elif bundle_pct > 15:
            risk += 15
            factors.append(f"Bundle elevated: {bundle_pct:.0f}%")

        # 狙击手
        sniper_pct = float(adv.get("sniperHoldPercent") or adv.get("sniperHoldingPct", 0))
        if sniper_pct > 20:
            risk += 20
            factors.append(f"High sniper: {sniper_pct:.0f}%")

        # 开发者
        dev_rug = int(adv.get("creatorRugCount") or adv.get("devRugCount", 0))
        dev_total = int(adv.get("creatorTokens") or adv.get("devTotalLaunches", 1))
        dev_rug_rate = dev_rug / max(dev_total, 1)
        if dev_rug_rate > self.max_dev_rug_rate:
            risk += 25
            factors.append(f"Dev rug rate: {dev_rug_rate:.0%}")

        # 风险等级
        risk_level = adv.get("riskLevelControl") or token_data.get("riskLevelControl", "1")
        if str(risk_level) in ("3", "4", "5"):
            risk += 30
            factors.append(f"Risk level: {risk_level}")

        # 新钱包占比
        new_wallet = float(adv.get("newWalletPercent") or adv.get("newWalletPct", 0))
        if new_wallet > 50:
            risk += 15
            factors.append(f"New wallets: {new_wallet:.0f}%")

        # top10集中度
        top10 = float(token_data.get("top10HoldPercent", 0))
        if top10 > 25:
            risk += 10
            factors.append(f"Top10 hold: {top10:.1f}%")

        return min(100, risk), factors
