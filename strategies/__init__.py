"""
H AI量化平台 — 策略模块
"""

from strategies.base import BaseStrategy, Signal
from strategies.momentum_breakout import MomentumBreakoutStrategy
from strategies.whale_tracking import WhaleTrackingStrategy
from strategies.new_token_snipe import NewTokenSnipeStrategy

__all__ = [
    "BaseStrategy", "Signal",
    "MomentumBreakoutStrategy",
    "WhaleTrackingStrategy",
    "NewTokenSnipeStrategy",
]
