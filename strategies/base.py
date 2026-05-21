"""策略基类 — 所有策略继承此基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Signal:
    """交易信号"""
    token_address: str
    token_symbol: str
    chain: str
    direction: str          # "long" | "short"
    confidence: float       # 0.0 - 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    def scan(self) -> list[Signal]:
        """扫描市场，返回信号列表"""
        ...

    @abstractmethod
    def analyze(self, token_address: str) -> Optional[dict]:
        """深度分析单个代币"""
        ...

    def log(self, msg: str):
        print(f"[{self.name}] {msg}")
