"""
自动交易机器人 — 每小时扫描 + 模拟执行 + 完整日志 + 记忆系统

用法:
  python scripts/auto_trader.py scan      扫描信号 (不执行)
  python scripts/auto_trader.py trade     扫描 + 买入 Top 5
  python scripts/auto_trader.py check     检查持仓 + 止盈止损
  python scripts/auto_trader.py report    生成完整交易报告
  python scripts/auto_trader.py memory    更新记忆文件
"""

import sys
import json
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PROJECT_ROOT, load_yaml_config as load_config
from paper_trade.wallet import SimulatedWallet
from strategies import (
    MomentumBreakoutStrategy,
    WhaleTrackingStrategy,
    NewTokenSnipeStrategy,
)
from data.fetcher import fetch_multi_prices

# 文件路径
STATE_FILE = PROJECT_ROOT / "data" / "auto_state.pkl"
TRADE_LOG = PROJECT_ROOT / "data" / "trade_log.json"
MEMORY_FILE = Path("C:/Users/Administrator/.claude/projects/C--Users-Administrator-Desktop-H-AI----/memory/trade_memory.md")

# 风控
STOP_LOSS = -0.20
TAKE_PROFIT = 0.45       # 从50%降至45%，避免+49%→反转
MAX_POSITIONS = 5
POSITION_SIZE = 400.0
COOLDOWN_ROUNDS = 2      # TP/SL后冷却轮次
MAX_SL_BEFORE_BAN = 2    # 触发N次止损后拉黑

# 黑名单 — 从交易日志自动学习
def load_blacklist(logger) -> set:
    """分析历史交易，返回应拉黑的代币地址"""
    banned = set()
    sl_counts = {}
    for r in logger.rounds:
        for e in r.get("exits", []):
            if e.get("reason") == "STOP_LOSS":
                addr = e["address"]
                sl_counts[addr] = sl_counts.get(addr, 0) + 1
                if sl_counts[addr] >= MAX_SL_BEFORE_BAN:
                    banned.add(addr)
    return banned


def get_cooldown_tokens(logger) -> set:
    """最近N轮已交易过的代币（TP或SL），需要冷却"""
    cooled = set()
    recent_rounds = logger.rounds[-COOLDOWN_ROUNDS:] if len(logger.rounds) >= COOLDOWN_ROUNDS else logger.rounds
    for r in recent_rounds:
        for e in r.get("exits", []):
            cooled.add(e["address"])
    return cooled


# ═══════════════════════════════════════════
# 交易日志系统
# ═══════════════════════════════════════════

class TradeLogger:
    """持久化交易日志"""

    def __init__(self):
        self.rounds: list[dict] = []
        self._load()

    def _load(self):
        if TRADE_LOG.exists():
            try:
                with open(TRADE_LOG, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.rounds = data.get("rounds", [])
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRADE_LOG, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "total_rounds": len(self.rounds),
                "rounds": self.rounds,
            }, f, ensure_ascii=False, indent=2, default=str)

    def start_round(self, round_num: int) -> dict:
        """开始新一轮"""
        r = {
            "round": round_num,
            "started_at": datetime.now().isoformat(),
            "entries": [],
            "exits": [],
            "snapshots": [],
            "observations": [],
            "summary": {},
        }
        self.rounds.append(r)
        self._save()
        return r

    def log_entry(self, round_num: int, symbol: str, address: str,
                  price: float, amount: float, cost: float,
                  confidence: float, reason: str):
        """记录入场"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "address": address,
            "entry_price": price,
            "amount": amount,
            "cost_usd": cost,
            "confidence": confidence,
            "reason": reason,
        }
        self.rounds[-1]["entries"].append(entry)
        self._save()

    def log_exit(self, round_num: int, symbol: str, address: str,
                 entry_price: float, exit_price: float,
                 change_pct: float, pnl_usd: float, reason: str):
        """记录出场"""
        exit_rec = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "address": address,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "change_pct": round(change_pct, 2),
            "pnl_usd": round(pnl_usd, 2),
            "reason": reason,
        }
        self.rounds[-1]["exits"].append(exit_rec)
        self._save()

    def add_snapshot(self, positions: list[dict], equity: float, pnl: float):
        """添加快照"""
        self.rounds[-1]["snapshots"].append({
            "timestamp": datetime.now().isoformat(),
            "equity": round(equity, 2),
            "unrealized_pnl": round(pnl, 2),
            "positions": positions,
        })
        self._save()

    def add_observation(self, note: str):
        """添加观察"""
        self.rounds[-1]["observations"].append({
            "timestamp": datetime.now().isoformat(),
            "note": note,
        })
        self._save()

    def close_round(self, wallet: SimulatedWallet):
        """结束本轮，写总结"""
        r = self.rounds[-1]
        entries = r["entries"]
        exits = r["exits"]

        total_cost = sum(e["cost_usd"] for e in entries)
        total_realized = sum(e["pnl_usd"] for e in exits)
        unrealized = sum(p.unrealized_pnl for p in wallet.positions.values())

        r["summary"] = {
            "closed_at": datetime.now().isoformat(),
            "entries_count": len(entries),
            "exits_count": len(exits),
            "total_invested": round(total_cost, 2),
            "realized_pnl": round(total_realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_equity": round(wallet.total_equity(), 2),
            "win_rate": round(
                len([e for e in exits if e["pnl_usd"] > 0]) / max(len(exits), 1) * 100, 1
            ) if exits else 0,
        }
        self._save()


# ═══════════════════════════════════════════
# 记忆系统
# ═══════════════════════════════════════════

def update_memory(wallet: SimulatedWallet, logger: TradeLogger):
    """更新永久记忆文件"""
    now = datetime.now().isoformat()[:19]

    positions = wallet.positions
    pos_lines = []
    for addr, pos in positions.items():
        chg = (pos.current_price - pos.avg_entry_price) / pos.avg_entry_price * 100 if pos.avg_entry_price > 0 else 0
        tag = "+" if pos.unrealized_pnl >= 0 else "-"
        pos_lines.append(
            f"| {pos.token_symbol} | ${pos.avg_entry_price:.6f} | ${pos.current_price:.6f} | "
            f"{tag}{abs(chg):.1f}% | {tag}${abs(pos.unrealized_pnl):.2f} |"
        )

    rounds = logger.rounds
    total_rounds = len(rounds)
    all_entries = sum(len(r["entries"]) for r in rounds)
    all_exits = sum(len(r["exits"]) for r in rounds)
    total_realized = sum(
        e["pnl_usd"] for r in rounds for e in r["exits"]
    )
    total_unrealized = wallet.total_unrealized_pnl()
    total_pnl = total_realized + total_unrealized

    # 计算胜率
    all_exit_recs = [e for r in rounds for e in r["exits"]]
    wins = [e for e in all_exit_recs if e["pnl_usd"] > 0]
    win_rate = len(wins) / max(len(all_exit_recs), 1) * 100

    content = f"""---
name: trade-memory
description: 自动交易机器人永久记忆 — 每30分钟更新
metadata:
  type: project
---

# 交易记忆 — 自动交易机器人

**最后更新**: {now}
**运行轮次**: {total_rounds} 轮
**总交易**: {all_entries} 笔入场 · {all_exits} 笔出场

## 当前持仓

| 代币 | 入场价 | 当前价 | 涨跌 | 浮盈 |
|------|--------|--------|------|------|
{chr(10).join(pos_lines) if pos_lines else '| (空仓) | - | - | - | - |'}

## 账户总览

| 指标 | 数值 |
|------|------|
| 总权益 | ${wallet.total_equity():,.2f} |
| 初始资金 | $10,010 |
| 已实现盈亏 | {total_realized:+,.2f} |
| 未实现盈亏 | {total_unrealized:+,.2f} |
| **总盈亏** | **{total_pnl:+,.2f}** |
| 胜率 | {win_rate:.1f}% ({len(wins)}/{len(all_exit_recs)}) |
| 手续费 | ${wallet.total_fees_paid():.4f} |

## 最近交易记录

"""
    # 最近10笔出场
    all_exits_sorted = sorted(all_exit_recs, key=lambda x: x["timestamp"], reverse=True)
    for e in all_exits_sorted[:10]:
        content += f"- {e['timestamp'][:19]} | {e['symbol']:10s} | "
        content += f"入场 ${e['entry_price']:.6f} → 出场 ${e['exit_price']:.6f} | "
        content += f"{e['change_pct']:+.1f}% | {e['pnl_usd']:+.2f} | {e['reason']}\n"

    if not all_exits_sorted:
        content += "(暂无平仓记录)\n"

    content += f"""
## 最近入场

"""
    all_entries_sorted = []
    for r in rounds:
        for e in r["entries"]:
            all_entries_sorted.append(e)
    all_entries_sorted.sort(key=lambda x: x["timestamp"], reverse=True)
    for e in all_entries_sorted[:10]:
        content += f"- {e['timestamp'][:19]} | {e['symbol']:10s} | "
        content += f"${e['entry_price']:.8f} | ${e['cost_usd']:.0f} | "
        content += f"置信度 {e['confidence']:.2f} | {e['reason'][:60]}\n"

    if not all_entries_sorted:
        content += "(暂无入场记录)\n"

    content += f"""
## 轮次摘要

"""
    for r in rounds[-10:]:
        s = r.get("summary", {})
        content += f"### 第{r['round']}轮 ({r.get('started_at', '?')[:19]})\n"
        content += f"- 入场: {s.get('entries_count', len(r['entries']))}笔 | "
        content += f"出场: {s.get('exits_count', len(r['exits']))}笔 | "
        content += f"已实现: ${s.get('realized_pnl', 0):+.2f} | "
        content += f"权益: ${s.get('total_equity', 0):,.2f}\n"

    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[MEMORY] Updated: {MEMORY_FILE}")


# ═══════════════════════════════════════════
# 交易命令
# ═══════════════════════════════════════════

def cmd_scan():
    """扫描信号"""
    cfg = load_config()
    strategies = _init_strategies(cfg)

    print("=" * 60)
    print(f"  Signal Scan — {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    all_signals = []
    for name, strat in strategies.items():
        print(f"\n[{name}]")
        try:
            signals = strat.scan()
            print(f"  {len(signals)} signals")
            for s in signals[:5]:
                print(f"  {s.token_symbol:12s} {s.direction:6s} "
                      f"conf={s.confidence:.2f} price={s.entry_price:.8f}")
                print(f"    {s.reason[:80]}")
            all_signals.extend(signals)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nTotal: {len(all_signals)} signals")
    return all_signals


def cmd_trade():
    """扫描 + 买入 Top 5"""
    logger = TradeLogger()
    wallet = _load_wallet()

    cfg = load_config()
    strategies = _init_strategies(cfg)

    # 计算轮次
    round_num = len(logger.rounds) + 1

    print("=" * 60)
    print(f"  AUTO TRADE — Round {round_num}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 开始新轮
    logger.start_round(round_num)

    # 1. 扫描
    print("\n[1] Scanning...")
    all_signals = []
    for name, strat in strategies.items():
        try:
            signals = strat.scan()
            all_signals.extend(signals)
            print(f"  [{name}] {len(signals)} signals")
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            logger.add_observation(f"[{name}] scan error: {e}")

    if not all_signals:
        print("  No signals found. Skipping.")
        logger.add_observation("No signals this round")
        logger.close_round(wallet)
        wallet.print_summary()
        update_memory(wallet, logger)
        return

    # 2. 黑名单 + 冷却过滤
    banned = load_blacklist(logger)
    cooldown = get_cooldown_tokens(logger)

    # 去重 + 排序 + 过滤
    seen = set()
    unique = []
    skipped_ban = []
    skipped_cool = []
    for s in sorted(all_signals, key=lambda x: x.confidence, reverse=True):
        if s.token_address in seen:
            continue
        seen.add(s.token_address)
        if s.token_address in banned:
            skipped_ban.append(s.token_symbol)
            continue
        if s.token_address in cooldown:
            skipped_cool.append(s.token_symbol)
            continue
        unique.append(s)

    if skipped_ban:
        print(f"  [BLACKLIST] Skipped: {', '.join(skipped_ban)}")
    if skipped_cool:
        print(f"  [COOLDOWN] Skipped: {', '.join(skipped_cool)}")

    top5 = unique[:MAX_POSITIONS]
    print(f"\n[2] Top {len(top5)} unique signals selected (filtered {len(skipped_ban)+len(skipped_cool)})")

    # 3. 获取实时价格
    addrs = [s.token_address for s in top5]
    try:
        live_prices = fetch_multi_prices(addrs, "solana")
    except Exception as e:
        print(f"  Price fetch error: {e}")
        live_prices = {}

    # 4. 执行买入
    print(f"\n[3] Executing buys...")
    print(f"  {'#':3s} {'Token':12s} {'Price':>14s} {'Size':>8s} {'Qty':>10s} {'Conf':>6s}")
    print(f"  {'-'*60}")

    for i, sig in enumerate(top5, 1):
        # 用实时价格更新
        lp = live_prices.get(sig.token_address, {})
        items = lp.get("data", [lp])
        if isinstance(items, list) and items:
            live_p = float(items[0].get("price", 0))
            if live_p > 0 and abs(live_p - sig.entry_price) / sig.entry_price < 0.5:
                sig.entry_price = live_p
                sig.stop_loss = live_p * 0.80
                sig.take_profit = live_p * 1.50

        size = min(POSITION_SIZE, wallet.get_balance("USDC") * 0.25)
        if size < 50:
            print(f"  [{i}] SKIP: insufficient balance")
            continue

        try:
            tx = wallet.buy(
                token_address=sig.token_address,
                token_symbol=sig.token_symbol,
                chain=sig.chain,
                amount_in=size,
                price=sig.entry_price,
            )
            logger.log_entry(
                round_num=round_num,
                symbol=sig.token_symbol,
                address=sig.token_address,
                price=sig.entry_price,
                amount=tx.amount,
                cost=size,
                confidence=sig.confidence,
                reason=sig.reason,
            )

            print(f"  [{i}] {sig.token_symbol:12s} {sig.entry_price:>14.8f} "
                  f"${size:>6.0f} {tx.amount:>10.4f} {sig.confidence:>5.2f}")
            print(f"      SL={sig.stop_loss:.8f} TP={sig.take_profit:.8f} | {sig.reason[:60]}")

        except Exception as e:
            print(f"  [{i}] {sig.token_symbol} ERROR: {e}")

    # 5. 保存
    _save_wallet(wallet)

    # 6. 首次快照
    pos_snap = _pos_snapshot(wallet)
    logger.add_snapshot(pos_snap, wallet.total_equity(), wallet.total_unrealized_pnl())
    logger.add_observation(
        f"Round {round_num} opened: {len(wallet.positions)} positions, "
        f"equity ${wallet.total_equity():,.2f}"
    )

    logger.close_round(wallet)
    wallet.print_summary()

    # 7. 更新记忆
    update_memory(wallet, logger)

    print(f"\n  Round {round_num} complete. Next check in 30 min.")
    print(f"  Run: python scripts/auto_trader.py check")


def cmd_check():
    """检查持仓 + 止盈止损"""
    logger = TradeLogger()
    wallet = _load_wallet()

    positions = wallet.positions
    if not positions:
        print("No open positions.")
        update_memory(wallet, logger)
        return

    round_num = len(logger.rounds)

    print("=" * 60)
    print(f"  POSITION CHECK — {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    # 获取实时价格
    addrs = list(positions.keys())
    try:
        prices = fetch_multi_prices(addrs, "solana")
    except Exception as e:
        print(f"Price fetch error: {e}")
        return

    price_map = {}
    for addr, data in prices.items():
        items = data.get("data", [data])
        p = float(items[0].get("price", 0)) if isinstance(items, list) and items else float(items.get("price", 0))
        if p > 0:
            price_map[addr] = p

    wallet.update_market_prices(price_map)

    # 打印持仓
    print(f"\n  {'Token':12s} {'Entry':>12s} {'Now':>12s} {'Chg%':>8s} {'PnL$':>10s} {'Signal':>8s}")
    print(f"  {'-'*65}")
    total_pnl = 0.0

    for addr, pos in positions.items():
        price = pos.current_price
        entry = pos.avg_entry_price
        chg = (price - entry) / entry * 100 if entry > 0 else 0
        pnl = pos.unrealized_pnl
        total_pnl += pnl

        sig = ""
        if chg <= STOP_LOSS * 100:
            sig = "[SL]"
        elif chg >= TAKE_PROFIT * 100:
            sig = "[TP]"

        print(f"  {pos.token_symbol:12s} {entry:>12.8f} {price:>12.8f} "
              f"{chg:>+7.2f}% ${pnl:>+9.2f} {sig:>8s}")

    print(f"  {'-'*65}")
    print(f"  Total PnL: ${total_pnl:+.2f} | Equity: ${wallet.total_equity():,.2f}")

    # 止盈止损检查
    exits = 0
    for addr, pos in list(positions.items()):
        chg = (pos.current_price - pos.avg_entry_price) / pos.avg_entry_price
        action = None
        if chg <= STOP_LOSS:
            action = "STOP_LOSS"
        elif chg >= TAKE_PROFIT:
            action = "TAKE_PROFIT"

        if action:
            try:
                # 在卖出前捕获盈亏
                pnl_before = pos.unrealized_pnl
                chg_before = chg
                tx = wallet.sell(addr, price=pos.current_price)
                logger.log_exit(
                    round_num=round_num,
                    symbol=pos.token_symbol,
                    address=addr,
                    entry_price=pos.avg_entry_price,
                    exit_price=pos.current_price,
                    change_pct=chg_before * 100,
                    pnl_usd=pnl_before,
                    reason=action,
                )
                tag = "[SL]" if action == "STOP_LOSS" else "[TP]"
                print(f"  {tag} {pos.token_symbol} closed: {chg_before:+.1%} PnL=${pnl_before:+.2f}")
                exits += 1
            except Exception as e:
                print(f"  Close error: {e}")

    if exits == 0:
        print(f"  [OK] All within risk range")

    # 快照
    pos_snap = _pos_snapshot(wallet)
    logger.add_snapshot(pos_snap, wallet.total_equity(), wallet.total_unrealized_pnl())
    logger.add_observation(
        f"Check: {len(positions)} positions, PnL ${total_pnl:+.2f}, "
        f"Exits: {exits}, Equity ${wallet.total_equity():,.2f}"
    )

    _save_wallet(wallet)
    update_memory(wallet, logger)


def cmd_report():
    """完整报告"""
    logger = TradeLogger()
    wallet = _load_wallet()

    print("=" * 60)
    print("  TRADE REPORT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    rounds = logger.rounds
    print(f"\n  Total Rounds: {len(rounds)}")

    all_entries = sum(len(r["entries"]) for r in rounds)
    all_exits = sum(len(r["exits"]) for r in rounds)
    print(f"  Total Entries: {all_entries} | Exits: {all_exits}")

    total_realized = sum(e["pnl_usd"] for r in rounds for e in r["exits"])
    print(f"  Realized PnL: ${total_realized:+,.2f}")
    print(f"  Unrealized PnL: ${wallet.total_unrealized_pnl():+,.2f}")
    print(f"  Total Equity: ${wallet.total_equity():,.2f}")

    # 按轮次
    for r in rounds:
        s = r.get("summary", {})
        if s:
            print(f"\n  Round {r['round']}: {s.get('entries_count',0)} in, "
                  f"{s.get('exits_count',0)} out, "
                  f"Realized ${s.get('realized_pnl',0):+.2f}, "
                  f"Equity ${s.get('total_equity',0):,.2f}")

    # 所有平仓交易
    all_exit_recs = [e for r in rounds for e in r["exits"]]
    if all_exit_recs:
        print(f"\n  All Closed Trades:")
        print(f"  {'Symbol':10s} {'Entry':>12s} {'Exit':>12s} {'Chg%':>8s} {'PnL$':>10s} {'Reason':>12s}")
        print(f"  {'-'*70}")
        for e in all_exit_recs:
            print(f"  {e['symbol']:10s} {e['entry_price']:>12.8f} {e['exit_price']:>12.8f} "
                  f"{e['change_pct']:>+7.1f}% ${e['pnl_usd']:>+9.2f} {e['reason']:>12s}")


def cmd_memory():
    """更新记忆文件"""
    logger = TradeLogger()
    wallet = _load_wallet()
    update_memory(wallet, logger)
    print("Memory updated.")


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def _init_strategies(cfg: dict) -> dict:
    trading_cfg = cfg.get("trading", {})
    chain = trading_cfg.get("default_chain", "solana")
    return {
        "momentum_breakout": MomentumBreakoutStrategy({"chain": chain}),
        "whale_tracking": WhaleTrackingStrategy({"chain": chain}),
        "new_token_snipe": NewTokenSnipeStrategy({"chain": chain}),
    }


def _load_wallet() -> SimulatedWallet:
    if STATE_FILE.exists():
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)["wallet"]
    return SimulatedWallet(10000, 10)


def _save_wallet(wallet: SimulatedWallet):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "wb") as f:
        pickle.dump({"wallet": wallet, "saved_at": datetime.now().isoformat()}, f)


def _pos_snapshot(wallet: SimulatedWallet) -> list[dict]:
    snaps = []
    for addr, pos in wallet.positions.items():
        chg = (pos.current_price - pos.avg_entry_price) / pos.avg_entry_price * 100 if pos.avg_entry_price > 0 else 0
        snaps.append({
            "symbol": pos.token_symbol,
            "address": addr,
            "entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price),
            "change_pct": round(float(chg), 2),
            "pnl": round(float(pos.unrealized_pnl), 2),
        })
    return snaps


# ═══════════════════════════ main ═══════════════════════

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "scan":
        cmd_scan()
    elif cmd == "trade":
        cmd_trade()
    elif cmd == "check":
        cmd_check()
    elif cmd == "report":
        cmd_report()
    elif cmd == "memory":
        cmd_memory()
    else:
        print("Usage: python scripts/auto_trader.py [scan|trade|check|report|memory]")


if __name__ == "__main__":
    main()
