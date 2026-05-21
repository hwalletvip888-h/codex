"""
信号分析与报告生成
"""

import pandas as pd
from strategies.base import Signal


def generate_signal_report(signals: list[Signal]) -> pd.DataFrame:
    """将策略信号汇总为 DataFrame"""
    rows = []
    for sig in signals:
        rows.append({
            "token": sig.token_symbol,
            "address": sig.token_address,
            "chain": sig.chain,
            "direction": sig.direction,
            "confidence": round(sig.confidence, 3),
            "entry_price": sig.entry_price,
            "stop_loss": sig.stop_loss,
            "take_profit": sig.take_profit,
            "reason": sig.reason,
        })
    return pd.DataFrame(rows)


def filter_high_confidence(signals: list[Signal], threshold: float = 0.7) -> list[Signal]:
    """筛选高置信度信号"""
    return [s for s in signals if s.confidence >= threshold]
