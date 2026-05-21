"""
模拟交易引擎 — 扫描 + 买入 + 自动止盈止损 + 持久化日志

用法:
  python scripts/sim_trade.py buy            扫描并买入 Top 5
  python scripts/sim_trade.py check          检查持仓 + 自动止盈止损
  python scripts/sim_trade.py monitor        持续监控 (每 N 秒)
  python scripts/sim_trade.py journal        查看完整日志
  python scripts/sim_trade.py status         当前状态
"""

import sys
import json
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PROJECT_ROOT, load_yaml_config as load_config
from paper_trade.wallet import SimulatedWallet

# 文件路径
STATE_FILE = PROJECT_ROOT / "data" / "sim_state.pkl"
JOURNAL_FILE = PROJECT_ROOT / "data" / "sim_journal.json"

# 风控参数
STOP_LOSS_PCT = -0.20        # -20% 止损
TAKE_PROFIT_PCT = 0.50       # +50% 止盈
TRAILING_STOP_PCT = 0.15     # 从高点回撤 15% 移动止盈
TRAILING_ACTIVATE_PCT = 0.60 # 盈利 60% 后激活移动止盈


# ═══════════════════════════════════════════
# 持久化日志系统
# ═══════════════════════════════════════════

@dataclass
class JournalEntry:
    """日志条目"""
    timestamp: str
    event: str           # ENTRY / EXIT / SNAPSHOT / OBSERVATION / SIGNAL
    token_symbol: str
    token_address: str
    price: float
    details: dict = field(default_factory=dict)


class SimulationJournal:
    """模拟日志持久库"""

    def __init__(self):
        self.entries: list[dict] = []
        self.observations: list[dict] = []
        self.snapshots: list[dict] = []
        self._load()

    def _load(self):
        """从磁盘加载"""
        if JOURNAL_FILE.exists():
            try:
                with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.entries = data.get("entries", [])
                self.observations = data.get("observations", [])
                self.snapshots = data.get("snapshots", [])
            except (json.JSONDecodeError, KeyError):
                # 备份损坏的日志
                import shutil
                backup = JOURNAL_FILE.with_suffix(".json.bak")
                shutil.copy2(JOURNAL_FILE, backup)
                print(f"[WARN] Journal corrupted, backed up to {backup}")

    def _save(self):
        """保存到磁盘"""
        data = {
            "updated_at": datetime.now().isoformat(),
            "entries": self.entries,
            "observations": self.observations,
            "snapshots": self.snapshots,
        }
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def log(self, event: str, token_symbol: str, token_address: str,
            price: float, **details):
        """记录事件"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "token_symbol": token_symbol,
            "token_address": token_address,
            "price": price,
            "details": details,
        }
        self.entries.append(entry)
        self._save()

    def observe(self, note: str, data: dict = None):
        """记录市场观察"""
        obs = {
            "timestamp": datetime.now().isoformat(),
            "note": note,
            "data": data or {},
        }
        self.observations.append(obs)
        self._save()

    def snapshot(self, positions: list[dict], equity: float, pnl: float):
        """记录持仓快照"""
        snap = {
            "timestamp": datetime.now().isoformat(),
            "equity": round(equity, 2),
            "unrealized_pnl": round(pnl, 2),
            "positions": positions,
        }
        self.snapshots.append(snap)
        self._save()

    def report(self) -> str:
        """生成简短报告"""
        if not self.entries:
            return "No journal entries yet."

        entries_by_event = {}
        for e in self.entries:
            ev = e["event"]
            entries_by_event[ev] = entries_by_event.get(ev, 0) + 1

        lines = [
            f"Journal: {len(self.entries)} entries, "
            f"{len(self.observations)} observations, "
            f"{len(self.snapshots)} snapshots",
            f"Events: {entries_by_event}",
        ]
        if self.snapshots:
            first = self.snapshots[0]
            last = self.snapshots[-1]
            lines.append(f"First snapshot: {first['timestamp'][:19]} "
                         f"Equity=${first['equity']:,.2f}")
            lines.append(f"Last snapshot:  {last['timestamp'][:19]} "
                         f"Equity=${last['equity']:,.2f}")
        return "\n".join(lines)


# ═══════════════════════════════════════════
# 风控引擎
# ═══════════════════════════════════════════

def check_risk(wallet: SimulatedWallet, journal: SimulationJournal,
               prices: dict[str, float]) -> list[dict]:
    """
    检查所有持仓的风险状态
    返回需要执行的行动列表
    """
    actions = []
    entry_map = _load_entry_map(journal)

    for addr, pos in wallet.positions.items():
        current_price = prices.get(addr, pos.current_price)
        if current_price <= 0:
            continue

        entry_price = pos.avg_entry_price
        change_pct = (current_price - entry_price) / entry_price

        # 检查之前的最高价 (用于移动止盈)
        peak_key = f"peak_{addr}"
        peak_price = _get_peak(journal, addr, current_price)

        action = None
        reason = ""

        # 1. 硬止损 (-20%)
        if change_pct <= STOP_LOSS_PCT:
            action = "STOP_LOSS"
            reason = f"Hard stop loss triggered: {change_pct:.1%}"

        # 2. 硬止盈 (+50%)
        elif change_pct >= TAKE_PROFIT_PCT:
            action = "TAKE_PROFIT"
            reason = f"Take profit triggered: {change_pct:.1%}"

        # 3. 移动止盈: 盈利 >60% 后从高点回撤 >15%
        elif change_pct >= TRAILING_ACTIVATE_PCT:
            drawdown_from_peak = (peak_price - current_price) / peak_price
            if drawdown_from_peak >= TRAILING_STOP_PCT:
                action = "TRAILING_STOP"
                reason = (f"Trailing stop: peak ${peak_price:.8f} -> "
                          f"${current_price:.8f} ({drawdown_from_peak:.1%} drawdown)")

        if action:
            actions.append({
                "action": action,
                "token_address": addr,
                "token_symbol": pos.token_symbol,
                "price": current_price,
                "change_pct": change_pct,
                "amount": pos.amount,
                "reason": reason,
            })

    return actions


def execute_actions(wallet: SimulatedWallet, journal: SimulationJournal,
                    actions: list[dict]) -> int:
    """执行风控行动"""
    executed = 0
    for a in actions:
        try:
            tx = wallet.sell(
                token_address=a["token_address"],
                price=a["price"],
            )
            journal.log(
                event="EXIT",
                token_symbol=a["token_symbol"],
                token_address=a["token_address"],
                price=a["price"],
                exit_reason=a["action"],
                change_pct=round(a["change_pct"] * 100, 1),
                pnl_usd=round(tx.total_value - (a["amount"] * a["price"] / (
                    1 + a["change_pct"] if a["change_pct"] > 0 else 1
                )), 2),  # approximate
                tx_id=tx.id,
                reason=a["reason"],
            )
            tag = {"STOP_LOSS": "[SL]", "TAKE_PROFIT": "[TP]",
                   "TRAILING_STOP": "[TS]"}.get(a["action"], "[?]")
            print(f"  {tag} {a['token_symbol']:12s} sold @ {a['price']:.8f} "
                  f"({a['change_pct']:+.1%}) | {a['reason']}")
            executed += 1
        except Exception as e:
            print(f"  [ERR] {a['token_symbol']}: {e}")
    return executed


def _load_entry_map(journal: SimulationJournal) -> dict:
    """从日志加载入场价映射"""
    entry_map = {}
    for e in journal.entries:
        if e["event"] == "ENTRY":
            entry_map[e["token_address"]] = e["price"]
    return entry_map


def _get_peak(journal: SimulationJournal, addr: str, current: float) -> float:
    """获取历史最高价"""
    peak = current
    for snap in journal.snapshots:
        for pos in snap.get("positions", []):
            if pos.get("address") == addr:
                p = pos.get("current_price", 0)
                if p > peak:
                    peak = p
    return peak


# ═══════════════════════════════════════════
# 命令
# ═══════════════════════════════════════════

def cmd_buy():
    """扫描信号并买入 Top 5"""
    from strategies import WhaleTrackingStrategy
    from data.fetcher import fetch_multi_prices

    journal = SimulationJournal()
    wallet, _ = _load_wallet()

    strategy = WhaleTrackingStrategy({"chain": "solana"})

    print("=" * 60)
    print("  Sim Trading - BUY Top 5 Signals")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n[1] Scanning whale signals...")
    signals = strategy.scan()
    print(f"    {len(signals)} raw signals")

    # 去重 + 排序
    seen = set()
    unique = []
    for s in sorted(signals, key=lambda x: x.confidence, reverse=True):
        if s.token_address not in seen:
            seen.add(s.token_address)
            unique.append(s)

    top5 = unique[:5]
    print(f"    {len(unique)} unique, selecting top 5\n")

    # 获取实时价格
    addrs = [s.token_address for s in top5]
    live_prices = fetch_multi_prices(addrs, "solana")

    # 更新信号入场价为实时价格
    for s in top5:
        lp = live_prices.get(s.token_address, {})
        items = lp.get("data", [lp])
        live_price = float(items[0].get("price", 0)) if isinstance(items, list) and items else 0
        if live_price > 0 and abs(live_price - s.entry_price) / s.entry_price < 0.5:
            s.entry_price = live_price
        if s.stop_loss == 0 or abs(s.stop_loss - s.entry_price * 0.85) / (s.entry_price * 0.85) < 0.01:
            s.stop_loss = s.entry_price * 0.80
        if s.take_profit == 0 or abs(s.take_profit - s.entry_price * 1.35) / (s.entry_price * 1.35) < 0.01:
            s.take_profit = s.entry_price * 1.50

    print("[2] Executing buys...")
    for i, sig in enumerate(top5, 1):
        size = min(400.0, wallet.get_balance("USDC") * 0.22)
        if size < 50:
            continue

        tx = wallet.buy(
            token_address=sig.token_address,
            token_symbol=sig.token_symbol,
            chain=sig.chain,
            amount_in=size,
            price=sig.entry_price,
        )

        journal.log(
            event="ENTRY",
            token_symbol=sig.token_symbol,
            token_address=sig.token_address,
            price=sig.entry_price,
            amount=tx.amount,
            cost=size,
            confidence=sig.confidence,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            reason=sig.reason,
            tx_id=tx.id,
        )

        print(f"  [{i}] {sig.token_symbol:12s} ${size:.0f} @ {sig.entry_price:.8f} "
              f"| Qty:{tx.amount:.2f} | Conf:{sig.confidence:.2f}")
        print(f"      SL:{sig.stop_loss:.8f} TP:{sig.take_profit:.8f} "
              f"| {sig.reason}")

    _save_wallet(wallet)
    journal.observe(f"Buy round: {len(top5)} positions opened")
    wallet.print_summary()
    print(f"\n  ENTRIES RECORDED. Run 'check' or 'monitor' to track.")


def cmd_check():
    """检查持仓 + 自动止盈止损"""
    journal = SimulationJournal()
    wallet, _ = _load_wallet()
    from data.fetcher import fetch_multi_prices

    print("=" * 60)
    print("  PnL CHECK + Auto Risk Management")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    positions = wallet.positions
    if not positions:
        print("\n  No open positions.")
        print(f"  {journal.report()}")
        return

    # 获取实时价格
    addrs = list(positions.keys())
    print(f"\n  Fetching prices for {len(addrs)} tokens...")
    prices = fetch_multi_prices(addrs, "solana")

    price_map = {}
    for addr, data in prices.items():
        items = data.get("data", [data])
        p = float(items[0].get("price", 0)) if isinstance(items, list) and items else float(items.get("price", 0))
        if p > 0:
            price_map[addr] = p

    wallet.update_market_prices(price_map)

    # 更新当前价格
    for addr, p in price_map.items():
        if addr in wallet.positions:
            wallet.positions[addr].current_price = p

    # 打印 PnL
    print(f"\n  PnL Table:")
    print(f"  {'Token':12s} {'Entry':>12s} {'Now':>12s} {'Chg%':>9s} {'PnL$':>10s} {'Signal':>10s}")
    print(f"  {'-'*68}")
    total_pnl = 0.0
    entry_map = {e["token_address"]: e for e in journal.entries if e["event"] == "ENTRY"}

    pos_snapshots = []
    for addr, pos in wallet.positions.items():
        entry = entry_map.get(addr, {})
        price = pos.current_price
        entry_p = pos.avg_entry_price
        chg = (price - entry_p) / entry_p * 100 if entry_p > 0 else 0
        pnl = pos.unrealized_pnl
        total_pnl += pnl

        # 信号判断
        if chg >= TAKE_PROFIT_PCT * 100:
            sig = "[TP]"
        elif chg <= STOP_LOSS_PCT * 100:
            sig = "[SL]"
        elif chg >= TRAILING_ACTIVATE_PCT * 100:
            sig = "[TRAIL]"
        else:
            sig = ""

        print(f"  {pos.token_symbol:12s} {entry_p:>12.8f} {price:>12.8f} "
              f"{chg:>+8.2f}% ${pnl:>+9.2f} {sig:>10s}")

        pos_snapshots.append({
            "symbol": pos.token_symbol,
            "address": addr,
            "entry_price": float(entry_p),
            "current_price": float(price),
            "change_pct": round(float(chg), 2),
            "pnl": round(float(pnl), 2),
            "amount": pos.amount,
        })

    print(f"  {'-'*68}")
    print(f"  Total Unrealized PnL: ${total_pnl:+.2f}")

    # 风险检查
    actions = check_risk(wallet, journal, price_map)
    if actions:
        print(f"\n  [!] Risk actions triggered: {len(actions)}")
        executed = execute_actions(wallet, journal, actions)
        if executed:
            _save_wallet(wallet)
    else:
        print(f"\n  [OK] All positions within risk parameters")

    # 保存快照
    journal.snapshot(pos_snapshots, wallet.total_equity(), total_pnl)

    # 自动生成观察笔记
    pos_summary = ", ".join(
        f"{p['symbol']} {p['change_pct']:+.1f}%"
        for p in pos_snapshots
    )
    journal.observe(
        f"AUTO CHECK: Equity ${wallet.total_equity():,.2f} | "
        f"Unrealized PnL ${total_pnl:+,.2f} | "
        f"Positions: {pos_summary}"
    )

    wallet.print_summary()
    print(f"\n  {journal.report()}")


def cmd_monitor():
    """持续监控模式 — 自动止盈止损"""
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300  # 默认5分钟
    print(f"Continuous monitor mode (interval: {interval}s)")
    print(f"Auto SL/TP/TS enabled | Stop: {STOP_LOSS_PCT:.0%} | TP: {TAKE_PROFIT_PCT:.0%} | Trail: {TRAILING_ACTIVATE_PCT:.0%}+")

    round_num = 0
    try:
        while True:
            round_num += 1
            print(f"\n{'='*55}")
            print(f"  Round {round_num} | {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*55}")
            cmd_check()
            print(f"\n  Next check in {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[STOP] Monitor ended")


def cmd_journal():
    """查看日志"""
    journal = SimulationJournal()

    print("=" * 60)
    print("  Simulation Journal")
    print("=" * 60)
    print(f"  {journal.report()}")
    print()

    # 最近交易
    entries = journal.entries
    if entries:
        print("  Recent Events:")
        for e in entries[-15:]:
            ts = e["timestamp"][:19]
            print(f"  {ts} | {e['event']:8s} | {e['token_symbol']:12s} "
                  f"@ {e['price']:.8f} | {e.get('details', {}).get('reason', '')}")

    # 快照
    snaps = journal.snapshots
    if snaps:
        print(f"\n  Equity Curve ({len(snaps)} points):")
        for s in snaps:
            ts = s["timestamp"][:19]
            print(f"  {ts} | Equity: ${s['equity']:,.2f} | PnL: ${s['unrealized_pnl']:+,.2f}")

    # 观察笔记
    obs = journal.observations
    if obs:
        print(f"\n  Observations ({len(obs)}):")
        for o in obs[-5:]:
            print(f"  {o['timestamp'][:19]} | {o['note']}")


def cmd_status():
    """当前状态"""
    wallet, _ = _load_wallet()
    journal = SimulationJournal()
    wallet.print_summary()
    print(f"\n  {journal.report()}")


# ═══════════════════════════════════════════
# 状态持久化
# ═══════════════════════════════════════════

def _load_wallet() -> tuple[SimulatedWallet, list]:
    if STATE_FILE.exists():
        with open(STATE_FILE, "rb") as f:
            state = pickle.load(f)
        return state["wallet"], state.get("entry_log", [])
    return SimulatedWallet(10000, 10), []


def _save_wallet(wallet: SimulatedWallet, entry_log: list = None):
    if entry_log is None:
        entry_log = []
    state = {"wallet": wallet, "entry_log": entry_log,
             "saved_at": datetime.now().isoformat()}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "wb") as f:
        pickle.dump(state, f)


# ═══════════════════════════ main ═══════════════════════

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "buy":
        cmd_buy()
    elif cmd == "check":
        cmd_check()
    elif cmd == "monitor":
        cmd_monitor()
    elif cmd == "journal":
        cmd_journal()
    elif cmd == "status":
        cmd_status()
    else:
        print("Usage: python scripts/sim_trade.py [buy|check|monitor|journal|status]")


if __name__ == "__main__":
    main()
