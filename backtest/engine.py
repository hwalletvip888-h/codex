"""
回测引擎 — 基于历史 OHLC 数据逐 bar 模拟交易执行
计算: 夏普比率 / 最大回撤 / 胜率 / 盈亏比 / 收益率曲线
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from strategies.base import BaseStrategy, Signal


@dataclass
class Bar:
    """单根 K 线"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SimulatedPosition:
    """回测持仓"""
    token_address: str
    token_symbol: str
    entry_price: float
    amount: float
    entry_time: datetime
    stop_loss: float
    take_profit: float

    def check_exit(self, bar: Bar) -> Optional[tuple[str, float]]:
        """检查是否触发止损/止盈, 返回 (exit_reason, exit_price)"""
        # 优先检查止损 (low 穿透)
        if bar.low <= self.stop_loss:
            return ("stop_loss", self.stop_loss)
        # 检查止盈 (high 穿透)
        if bar.high >= self.take_profit:
            return ("take_profit", self.take_profit)
        return None


@dataclass
class CompletedTrade:
    """已完成交易"""
    token_symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    pnl_pct: float
    exit_reason: str


class BacktestEngine:
    """完整回测引擎"""

    def __init__(self, initial_capital: float = 10000.0, fee_bps: float = 25.0,
                 slippage_bps: float = 50.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee_rate = fee_bps / 10000
        self.slippage_rate = slippage_bps / 10000

        self.positions: list[SimulatedPosition] = []
        self.closed_trades: list[CompletedTrade] = []
        self.equity_curve: list[dict] = []

    # ── 核心 ──

    def run_on_bars(self, bars: list[Bar], strategy_signals: list[dict],
                    token_address: str = "unknown") -> pd.DataFrame:
        """
        基于 K 线序列 + 策略信号 逐 bar 模拟
        strategy_signals: [{"bar_index": int, "direction": "long"/"short", "confidence": float}, ...]
        """
        signal_map = {}
        for s in strategy_signals:
            signal_map[s.get("bar_index", 0)] = s

        for i, bar in enumerate(bars):
            # 1. 检查持仓退出
            for pos in list(self.positions):
                exit_check = pos.check_exit(bar)
                if exit_check:
                    reason, exit_price = exit_check
                    self._close_position(pos, exit_price, bar.timestamp, reason)

            # 2. 检查信号入场
            if i in signal_map:
                sig = signal_map[i]
                self._process_signal(sig, bar, token_address)

            # 3. 记录权益曲线
            equity = self._calc_equity(bar.close)
            self.equity_curve.append({
                "timestamp": bar.timestamp,
                "equity": equity,
                "price": bar.close,
            })

        return pd.DataFrame(self.equity_curve)

    def _process_signal(self, sig: dict, bar: Bar, token_address: str):
        """处理信号: 决定是否开仓"""
        direction = sig.get("direction", "long")
        confidence = sig.get("confidence", 0.5)
        if direction != "long" or confidence < 0.4:
            return

        # 仓位计算: 凯利公式简化版
        position_pct = min(0.20, confidence * 0.25)
        position_value = self.capital * position_pct

        entry_price = bar.close * (1 + self.slippage_rate)
        amount = position_value / entry_price
        cost = position_value * (1 + self.fee_rate)

        if cost > self.capital * 0.3:
            return

        self.capital -= cost

        stop_loss = entry_price * (1 - sig.get("stop_loss_pct", 0.08))
        take_profit = entry_price * (1 + sig.get("take_profit_pct", 0.20))

        self.positions.append(SimulatedPosition(
            token_address=token_address,
            token_symbol=sig.get("symbol", token_address[:8]),
            entry_price=entry_price,
            amount=amount,
            entry_time=bar.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ))

    def _close_position(self, pos: SimulatedPosition, exit_price: float,
                        exit_time: datetime, reason: str):
        """平仓"""
        gross = pos.amount * exit_price
        fee = gross * self.fee_rate
        net = gross - fee
        cost = pos.amount * pos.entry_price * (1 + self.fee_rate)
        pnl = net - cost

        self.capital += net
        self.closed_trades.append(CompletedTrade(
            token_symbol=pos.token_symbol,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            amount=pos.amount,
            pnl=pnl,
            pnl_pct=pnl / cost * 100 if cost > 0 else 0,
            exit_reason=reason,
        ))
        self.positions.remove(pos)

    def _calc_equity(self, current_price: float) -> float:
        """计算当前总权益"""
        pos_value = sum(p.amount * current_price for p in self.positions)
        return self.capital + pos_value

    # ── 指标计算 ──

    def calc_metrics(self) -> dict:
        """计算回测核心指标"""
        if not self.equity_curve:
            return {"error": "无数据"}

        df = pd.DataFrame(self.equity_curve)
        returns = df["equity"].pct_change().dropna()

        # 总收益
        final_equity = df["equity"].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # 夏普比率 (年化, 假设 15min bar)
        if len(returns) > 1 and returns.std() > 0:
            n_bars_per_year = 365 * 24 * 4  # 15min bar
            sharpe = (returns.mean() / returns.std()) * np.sqrt(n_bars_per_year)
        else:
            sharpe = 0.0

        # 最大回撤
        cummax = df["equity"].cummax()
        drawdown = (df["equity"] - cummax) / cummax * 100
        max_drawdown = drawdown.min()

        # 胜率
        wins = [t for t in self.closed_trades if t.pnl > 0]
        win_rate = len(wins) / max(len(self.closed_trades), 1) * 100

        # 盈亏比
        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        losses = [t for t in self.closed_trades if t.pnl <= 0]
        avg_loss = np.mean([abs(t.pnl) for t in losses]) if losses else 0
        profit_factor = (sum(t.pnl for t in wins) /
                         max(abs(sum(t.pnl for t in losses)), 1))

        # 按退出原因统计
        exit_reasons = {}
        for t in self.closed_trades:
            exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "total_trades": len(self.closed_trades),
            "win_rate_pct": round(win_rate, 1),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "exit_reasons": exit_reasons,
        }

    def report(self) -> str:
        """生成回测报告"""
        m = self.calc_metrics()
        return (
            f"\n{'='*55}\n"
            f"  回测报告\n"
            f"{'='*55}\n"
            f"  初始资金:     ${m.get('initial_capital', 0):,.2f}\n"
            f"  最终权益:     ${m.get('final_equity', 0):,.2f}\n"
            f"  总收益率:     {m.get('total_return_pct', 0):+.2f}%\n"
            f"  夏普比率:     {m.get('sharpe_ratio', 0):.2f}\n"
            f"  最大回撤:     {m.get('max_drawdown_pct', 0):.2f}%\n"
            f"  总交易数:     {m.get('total_trades', 0)}\n"
            f"  胜率:         {m.get('win_rate_pct', 0):.1f}%\n"
            f"  平均盈利:     ${m.get('avg_win', 0):,.2f}\n"
            f"  平均亏损:     ${m.get('avg_loss', 0):,.2f}\n"
            f"  盈亏因子:     {m.get('profit_factor', 0):.2f}\n"
            f"  退出统计:     {m.get('exit_reasons', {})}\n"
            f"{'='*55}"
        )
