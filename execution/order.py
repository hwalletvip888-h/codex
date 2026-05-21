"""
交易执行层 — 订单管理与链上执行
"""

from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


@dataclass
class Order:
    token_address: str
    side: OrderSide
    amount_in: float
    slippage_bps: int = 100
    status: OrderStatus = OrderStatus.PENDING

    def submit(self) -> bool:
        """提交订单到链上（占位）"""
        self.status = OrderStatus.SUBMITTED
        return True
