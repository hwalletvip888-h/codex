"""
模拟钱包 — 虚拟余额管理 + 持仓跟踪 + 盈亏计算
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """持仓"""
    token_address: str
    token_symbol: str
    chain: str
    amount: float           # 持仓数量
    avg_entry_price: float  # 均价
    current_price: float    # 当前市价
    opened_at: datetime = field(default_factory=datetime.now)

    @property
    def cost_basis(self) -> float:
        return self.amount * self.avg_entry_price

    @property
    def market_value(self) -> float:
        return self.amount * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


@dataclass
class Transaction:
    """交易记录"""
    id: str
    token_address: str
    token_symbol: str
    side: str              # BUY / SELL
    amount: float
    price: float
    total_value: float     # amount * price (正数)
    fee: float
    timestamp: datetime = field(default_factory=datetime.now)


class SimulatedWallet:
    """模拟纸交易钱包"""

    def __init__(self, initial_usdc: float = 10000.0, initial_sol: float = 10.0):
        # 基础余额
        self.balances: dict[str, float] = {
            "USDC": initial_usdc,
            "SOL": initial_sol,
        }
        # 持仓 {token_address: Position}
        self.positions: dict[str, Position] = {}
        # 交易历史
        self.transactions: list[Transaction] = []
        # 计数器
        self._tx_counter = 0

        # 手续费配置
        self.fee_bps = 25          # 0.25% DEX 手续费
        self.priority_fee_sol = 0.00005  # Solana 优先费

    # ── 余额操作 ──

    def get_balance(self, asset: str) -> float:
        return self.balances.get(asset.upper(), 0.0)

    def _deduct(self, asset: str, amount: float):
        a = asset.upper()
        if self.balances.get(a, 0.0) < amount:
            raise ValueError(f"余额不足: {a} 需要 {amount} 持有 {self.balances.get(a, 0.0)}")
        self.balances[a] -= amount

    def _credit(self, asset: str, amount: float):
        a = asset.upper()
        self.balances[a] = self.balances.get(a, 0.0) + amount

    # ── 交易操作 ──

    def buy(self, token_address: str, token_symbol: str, chain: str,
            amount_in: float, price: float, quote_asset: str = "USDC") -> Transaction:
        """
        模拟买入: 用 quote_asset 购买 amount_in 价值的代币
        返回成交的 Transaction
        """
        fee = amount_in * self.fee_bps / 10000
        total_cost = amount_in + fee

        self._deduct(quote_asset, total_cost)

        token_amount = amount_in / price

        # 更新持仓
        if token_address in self.positions:
            pos = self.positions[token_address]
            new_total = pos.amount + token_amount
            pos.avg_entry_price = (
                (pos.cost_basis + amount_in) / new_total
            )
            pos.amount = new_total
            pos.current_price = price
        else:
            self.positions[token_address] = Position(
                token_address=token_address,
                token_symbol=token_symbol,
                chain=chain,
                amount=token_amount,
                avg_entry_price=price,
                current_price=price,
            )

        self._credit("SOL", -self.priority_fee_sol)  # 扣 gas

        self._tx_counter += 1
        tx = Transaction(
            id=f"TX#{self._tx_counter:05d}",
            token_address=token_address,
            token_symbol=token_symbol,
            side="BUY",
            amount=token_amount,
            price=price,
            total_value=amount_in,
            fee=fee + self.priority_fee_sol,
        )
        self.transactions.append(tx)
        return tx

    def sell(self, token_address: str, amount: Optional[float] = None,
             sell_pct: Optional[float] = None, price: Optional[float] = None,
             quote_asset: str = "USDC") -> Transaction:
        """
        模拟卖出: 卖出指定数量或比例的持仓代币
        """
        if token_address not in self.positions:
            raise ValueError(f"未持有该代币: {token_address}")

        pos = self.positions[token_address]
        price = price or pos.current_price

        if amount is None and sell_pct is not None:
            amount = pos.amount * sell_pct
        elif amount is None:
            amount = pos.amount  # 默认全卖

        if amount > pos.amount:
            raise ValueError(f"卖出数量超过持仓: {amount} > {pos.amount}")

        gross_value = amount * price
        fee = gross_value * self.fee_bps / 10000
        net_value = gross_value - fee

        self._credit(quote_asset, net_value)

        # 更新持仓
        pos.amount -= amount
        if pos.amount <= 1e-10:
            del self.positions[token_address]

        self._credit("SOL", -self.priority_fee_sol)

        self._tx_counter += 1
        tx = Transaction(
            id=f"TX#{self._tx_counter:05d}",
            token_address=token_address,
            token_symbol=pos.token_symbol,
            side="SELL",
            amount=amount,
            price=price,
            total_value=net_value,
            fee=fee + self.priority_fee_sol,
        )
        self.transactions.append(tx)
        return tx

    def update_market_prices(self, prices: dict[str, float]):
        """批量更新持仓市价 {token_address: price}"""
        for addr, price in prices.items():
            if addr in self.positions:
                self.positions[addr].current_price = price

    # ── 统计 ──

    def total_equity(self) -> float:
        """总权益 = 现金余额 + 持仓市值"""
        equity = sum(self.balances.values())
        for pos in self.positions.values():
            equity += pos.market_value
        return equity

    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    def total_fees_paid(self) -> float:
        return sum(tx.fee for tx in self.transactions)

    def realized_pnl_summary(self) -> dict:
        """已实现盈亏汇总"""
        sells = [tx for tx in self.transactions if tx.side == "SELL"]
        buys = {tx.token_address: tx for tx in self.transactions if tx.side == "BUY"}
        total_realized = 0.0
        for sell in sells:
            buy = buys.get(sell.token_address)
            if buy:
                total_realized += (sell.price - buy.price) * sell.amount
        return {
            "total_realized_pnl": total_realized,
            "total_trades": len(sells),
        }

    def summary(self) -> dict:
        """钱包总览"""
        return {
            "balances": dict(self.balances),
            "positions": len(self.positions),
            "total_equity": round(self.total_equity(), 2),
            "unrealized_pnl": round(self.total_unrealized_pnl(), 2),
            "total_fees": round(self.total_fees_paid(), 4),
            "total_txs": len(self.transactions),
        }

    def print_summary(self):
        """打印钱包状态"""
        print("\n" + "=" * 55)
        print("  [Wallet Status]")
        print("=" * 55)
        print(f"  Total Equity:  ${self.total_equity():>10,.2f}")
        print(f"  Balances:")
        for asset, amount in self.balances.items():
            print(f"    {asset:<8} ${amount:>10,.2f}")
        print(f"  Positions ({len(self.positions)}):")
        for pos in self.positions.values():
            tag = "[+]" if pos.unrealized_pnl >= 0 else "[-]"
            print(f"    {tag} {pos.token_symbol:<10} x{pos.amount:<10.4f}  "
                  f"avg${pos.avg_entry_price:<8.4f}  now${pos.current_price:<8.4f}  "
                  f"PnL: ${pos.unrealized_pnl:+.2f}")
        print(f"  Transactions: {len(self.transactions)}")
        print(f"  Total Fees: ${self.total_fees_paid():.4f}")
        print("=" * 55)
