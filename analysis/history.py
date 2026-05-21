"""
历史数据深度分析 — 多维度链上数据观测与可视化

功能:
- 价格趋势分析 (多周期 K线、均线、波动率)
- 聪明钱行为分析 (历史操作、胜率、跟单信号)
- 持仓集中度分析 (holder cluster、巨鲸占比)
- 交易流分析 (买卖比、净流量、大单检测)
- 代币对比分析
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from data.fetcher import (
    fetch_ohlc, fetch_token_trades, fetch_token_info,
    fetch_top_traders, fetch_token_holders, fetch_token_advanced,
)


def analyze_price_trend(token: str, chain: str = "solana",
                        intervals: list[str] = None) -> dict:
    """多周期价格趋势分析"""
    if intervals is None:
        intervals = ["5m", "15m", "1h", "4h"]

    results = {}
    for interval in intervals:
        limit = {"5m": 96, "15m": 96, "1h": 72, "4h": 48}.get(interval, 48)
        try:
            candles = fetch_ohlc(token, chain, interval=interval, limit=limit)
        except Exception as e:
            results[interval] = {"error": str(e)}
            continue

        if not candles:
            results[interval] = {"error": "无数据"}
            continue

        closes = np.array([float(c.get("close", c.get("c", 0))) for c in candles])
        highs = np.array([float(c.get("high", c.get("h", 0))) for c in candles])
        lows = np.array([float(c.get("low", c.get("l", 0))) for c in candles])
        volumes = np.array([float(c.get("volume", c.get("v", 0))) for c in candles])

        current = closes[-1]
        ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else current
        ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else current
        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else current

        # 波动率
        returns = np.diff(closes) / np.maximum(closes[:-1], 1e-10)
        volatility = float(np.std(returns) * np.sqrt(len(closes)))

        # 趋势判断
        trend = "up" if current > ma20 > ma50 else "down" if current < ma20 < ma50 else "sideways"

        results[interval] = {
            "current_price": round(float(current), 8),
            "ma5": round(float(ma5), 8),
            "ma20": round(float(ma20), 8),
            "ma50": round(float(ma50), 8),
            "high_period": round(float(np.max(highs)), 8),
            "low_period": round(float(np.min(lows)), 8),
            "volatility": round(volatility, 4),
            "trend": trend,
            "avg_volume": round(float(np.mean(volumes)), 0),
            "candle_count": len(candles),
        }

    return results


def analyze_smart_money(token: str, chain: str = "solana") -> dict:
    """聪明钱行为分析"""
    try:
        traders = fetch_top_traders(token, chain)
    except Exception as e:
        return {"error": str(e)}

    items = traders if isinstance(traders, list) else traders.get("traders", traders.get("data", []))
    buys = [t for t in items if str(t.get("side", "")).lower() == "buy"]
    sells = [t for t in items if str(t.get("side", "")).lower() == "sell"]

    total_buy_vol = sum(float(t.get("amount_usd", t.get("amount", 0))) for t in buys)
    total_sell_vol = sum(float(t.get("amount_usd", t.get("amount", 0))) for t in sells)

    avg_winrate = 0
    if items:
        winrates = [float(t.get("win_rate", t.get("winrate", 0))) for t in items]
        avg_winrate = sum(winrates) / max(len(winrates), 1)

    return {
        "smart_money_count": len(items),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "net_flow_usd": round(total_buy_vol - total_sell_vol, 2),
        "total_buy_vol": round(total_buy_vol, 2),
        "total_sell_vol": round(total_sell_vol, 2),
        "avg_winrate": round(avg_winrate, 3),
        "sentiment": "Bullish" if len(buys) > len(sells) else "Bearish" if len(sells) > len(buys) else "Neutral",
        "top_traders": [
            {
                "address": t.get("address", t.get("trader", "?"))[:12],
                "side": t.get("side", "?"),
                "amount_usd": t.get("amount_usd", t.get("amount", 0)),
                "win_rate": t.get("win_rate", t.get("winrate", 0)),
            }
            for t in items[:10]
        ],
    }


def analyze_holder_concentration(token: str, chain: str = "solana") -> dict:
    """持仓集中度分析"""
    try:
        holders = fetch_token_holders(token, chain, limit=100)
    except Exception as e:
        return {"error": str(e)}

    items = holders if isinstance(holders, list) else holders.get("holders", holders.get("data", []))
    if not items:
        return {"error": "无持仓数据"}

    total_pct = 0
    whale_count = 0
    pcts = []
    for h in items:
        pct = float(h.get("percentage", h.get("pct", 0)))
        pcts.append(pct)
        total_pct += pct
        if pct >= 1.0:
            whale_count += 1

    top5 = sum(sorted(pcts, reverse=True)[:5])
    top10 = sum(sorted(pcts, reverse=True)[:10])
    gini_like = top10 / max(total_pct, 0.01)  # 简化集中度指标

    risk = "low" if top10 < 30 else "medium" if top10 < 50 else "high" if top10 < 70 else "critical"

    return {
        "holder_count_shown": len(items),
        "whale_count_1pct": whale_count,
        "top5_concentration": round(top5, 1),
        "top10_concentration": round(top10, 1),
        "concentration_index": round(gini_like, 2),
        "risk_level": risk,
        "risk_emoji": {"low": "[LOW]", "medium": "[MED]", "high": "[HIGH]", "critical": "[CRIT]"}.get(risk, "[?]"),
    }


def analyze_trade_flow(token: str, chain: str = "solana", lookback: int = 50) -> dict:
    """交易流分析"""
    try:
        trades = fetch_token_trades(token, chain, limit=lookback)
    except Exception as e:
        return {"error": str(e)}

    if not trades:
        return {"error": "无交易数据"}

    buys = []
    sells = []
    for t in trades:
        side = str(t.get("side", "")).lower()
        amount = float(t.get("amount_usd", t.get("amount", 0)))
        price = float(t.get("price", 0))
        if side == "buy":
            buys.append({"amount": amount, "price": price})
        elif side == "sell":
            sells.append({"amount": amount, "price": price})

    total_buy = sum(b["amount"] for b in buys)
    total_sell = sum(s["amount"] for s in sells)
    avg_buy_size = total_buy / max(len(buys), 1)
    avg_sell_size = total_sell / max(len(sells), 1)

    # 大单检测 (>3x 均价)
    large_threshold = avg_buy_size * 3
    large_trades = [
        t for t in trades
        if float(t.get("amount_usd", t.get("amount", 0))) > large_threshold
    ]

    return {
        "total_trades": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "buy_sell_ratio": round(len(buys) / max(len(sells), 1), 2),
        "total_buy_vol": round(total_buy, 0),
        "total_sell_vol": round(total_sell, 0),
        "net_flow": round(total_buy - total_sell, 0),
        "avg_buy_size": round(avg_buy_size, 0),
        "avg_sell_size": round(avg_sell_size, 0),
        "large_trade_count": len(large_trades),
        "large_trade_pct": round(len(large_trades) / max(len(trades), 1) * 100, 1),
        "sentiment": "Bullish" if total_buy > total_sell * 1.3 else "Bearish" if total_sell > total_buy * 1.3 else "Neutral",
    }


def full_deep_dive(token: str, chain: str = "solana") -> dict:
    """完整深度分析 — 汇总所有维度"""
    print(f"\n>>> Deep Analysis: {token}")
    print("=" * 60)

    results = {
        "token": token,
        "chain": chain,
        "analyzed_at": datetime.now().isoformat(),
    }

    # 1. 基础信息
    print("\n[1/6] Token basic info...")
    try:
        info = fetch_token_info(token, chain)
        results["token_info"] = info
        print(f"  [OK]")
    except Exception as e:
        results["token_info"] = {"error": str(e)}
        print(f"  [FAIL] {e}")

    # 2. Advanced risk
    print("[2/6] Advanced risk analysis...")
    try:
        adv = fetch_token_advanced(token, chain)
        results["advanced"] = adv
        print(f"  [OK]")
    except Exception as e:
        results["advanced"] = {"error": str(e)}
        print(f"  [FAIL] {e}")

    # 3. 价格趋势 (多周期)
    print("[3/6] Multi-timeframe price trend...")
    results["price_trend"] = analyze_price_trend(token, chain)

    # 4. 聪明钱
    print("[4/6] Smart money analysis...")
    results["smart_money"] = analyze_smart_money(token, chain)

    # 5. 持仓集中度
    print("[5/6] Holder concentration...")
    results["holder_concentration"] = analyze_holder_concentration(token, chain)

    # 6. 交易流
    print("[6/6] Trade flow analysis...")
    results["trade_flow"] = analyze_trade_flow(token, chain)

    print("\n" + "=" * 60)
    return results


def print_deep_dive(results: dict):
    """精美打印深度分析结果"""
    print("\n" + "=" * 60)
    print("  H AI Quant Platform - Deep Analysis Report")
    print("=" * 60)

    # 价格趋势
    pt = results.get("price_trend", {})
    if pt:
        print("\n── 价格趋势 ──")
        for interval, data in pt.items():
            if isinstance(data, dict) and "error" not in data:
                arrow = {"up": "↗", "down": "↘", "sideways": "→"}.get(data["trend"], "?")
                print(f"  {interval:5s} ${data['current_price']:.6f}  "
                      f"MA20:${data['ma20']:.6f}  {arrow} {data['trend']}  "
                      f"波:{data['volatility']:.3f}")

    # 聪明钱
    sm = results.get("smart_money", {})
    if sm and "error" not in sm:
        print(f"\n── 聪明钱 ──")
        print(f"  交易者: {sm.get('smart_money_count', 0)}  买:{sm.get('buy_count', 0)}  卖:{sm.get('sell_count', 0)}")
        print(f"  净流量: ${sm.get('net_flow_usd', 0):,.0f}  均胜率: {sm.get('avg_winrate', 0):.1%}")
        print(f"  情绪: {sm.get('sentiment', '?')}")

    # 持仓
    hc = results.get("holder_concentration", {})
    if hc and "error" not in hc:
        print(f"\n── 持仓集中度 ──")
        print(f"  前5: {hc.get('top5_concentration', 0):.1f}%  前10: {hc.get('top10_concentration', 0):.1f}%")
        print(f"  巨鲸(>1%): {hc.get('whale_count_1pct', 0)}  风险: {hc.get('risk_emoji', '')} {hc.get('risk_level', '')}")

    # 交易流
    tf = results.get("trade_flow", {})
    if tf and "error" not in tf:
        print(f"\n── 交易流 (最近 {tf.get('total_trades', 0)} 笔) ──")
        print(f"  买卖比: {tf.get('buy_sell_ratio', 0):.1f}  净流: ${tf.get('net_flow', 0):,.0f}")
        print(f"  大单: {tf.get('large_trade_count', 0)} 笔 ({tf.get('large_trade_pct', 0):.0f}%)")
        print(f"  情绪: {tf.get('sentiment', '?')}")

    print("\n" + "=" * 60)
