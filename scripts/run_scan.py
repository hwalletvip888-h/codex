"""
H AI量化平台 -- 主运行脚本
流水线: 策略扫描 -> 信号汇总 -> 模拟执行 -> 持续监控

用法:
  python scripts/run_scan.py                    # 单次扫描
  python scripts/run_scan.py watch              # 持续监控模式
  python scripts/run_scan.py backtest --token <ADDR>  # 回测
  python scripts/run_scan.py analyze --token <ADDR>   # 深度分析
  python scripts/run_scan.py observe --token <ADDR>   # 历史数据观测
"""

import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PROJECT_ROOT
from config.settings import load_yaml_config
from strategies import (
    MomentumBreakoutStrategy,
    WhaleTrackingStrategy,
    NewTokenSnipeStrategy,
)
from analysis.reporter import generate_signal_report, filter_high_confidence
from paper_trade.wallet import SimulatedWallet


def load_config():
    """Load YAML config"""
    import yaml
    cfg_path = PROJECT_ROOT / "config" / "settings.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_strategies(cfg: dict) -> dict:
    """Initialize enabled strategies from config"""
    strategy_cfgs = cfg.get("strategies", {})
    enabled = strategy_cfgs.get("enabled", [])
    trading_cfg = cfg.get("trading", {})

    strategy_map = {
        "momentum_breakout": MomentumBreakoutStrategy,
        "whale_tracking": WhaleTrackingStrategy,
        "new_token_snipe": NewTokenSnipeStrategy,
    }

    instances = {}
    for name in enabled:
        cls = strategy_map.get(name)
        if cls is None:
            print(f"[WARN] Unknown strategy: {name}")
            continue
        s_cfg = strategy_cfgs.get(name, {})
        s_cfg.setdefault("chain", trading_cfg.get("default_chain", "solana"))
        instances[name] = cls(s_cfg)
        print(f"[OK] Loaded: {name}")

    return instances


def scan_all(strategies: dict) -> list:
    """Run all strategies, collect signals"""
    all_signals = []
    for name, strat in strategies.items():
        print(f"\n--- Scanning: {name} ---")
        try:
            signals = strat.scan()
            print(f"  Produced {len(signals)} signals")
            for s in signals:
                print(f"  -> {s.token_symbol:12s} {s.direction:6s} "
                      f"conf:{s.confidence:.2f} entry:{s.entry_price:.6f} "
                      f"SL:{s.stop_loss:.6f} TP:{s.take_profit:.6f}")
                print(f"     Reason: {s.reason}")
            all_signals.extend(signals)
        except Exception as e:
            print(f"  [ERROR] {e}")

    return all_signals


def execute_signals(wallet: SimulatedWallet, signals: list, max_per_signal: float = 500.0):
    """Execute high-confidence signals on simulated wallet"""
    high_conf = filter_high_confidence(signals, threshold=0.55)
    high_conf.sort(key=lambda s: s.confidence, reverse=True)

    executed = 0
    for sig in high_conf[:5]:  # max 5 concurrent
        if sig.direction != "long":
            continue
        try:
            amount = min(max_per_signal * sig.confidence,
                         wallet.get_balance("USDC") * 0.2)
            if amount < 50:
                print(f"  [SKIP] {sig.token_symbol} insufficient balance")
                continue

            tx = wallet.buy(
                token_address=sig.token_address,
                token_symbol=sig.token_symbol,
                chain=sig.chain,
                amount_in=amount,
                price=sig.entry_price,
            )
            print(f"  [BUY] {sig.token_symbol} ${amount:.0f} @ {sig.entry_price:.6f} "
                  f"conf:{sig.confidence:.2f} | {tx.id}")
            executed += 1
        except Exception as e:
            print(f"  [ERROR] {sig.token_symbol}: {e}")

    return executed


def watch_loop(strategies: dict, wallet: SimulatedWallet,
               interval: int = 60, rounds: int = 0):
    """Continuous monitoring loop"""
    print(f"\n>> Continuous monitoring (interval {interval}s, 'q' to quit)...")
    round_num = 0

    try:
        while rounds == 0 or round_num < rounds:
            round_num += 1
            print(f"\n{'='*50}")
            print(f" Round {round_num} | {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*50}")

            signals = scan_all(strategies)
            if signals:
                executed = execute_signals(wallet, signals)
                print(f"\n  Executed: {executed} trades")
            else:
                print("  No signals")

            wallet.print_summary()

            print(f"\nWaiting {interval}s...")
            try:
                for _ in range(interval):
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[STOP] User interrupt")
                break
    except KeyboardInterrupt:
        print("\n[STOP] Monitoring ended")

    wallet.print_summary()


def cmd_backtest(args):
    """Backtest mode"""
    from data.fetcher import fetch_ohlc
    from backtest.engine import BacktestEngine, Bar

    token = args.token or "So11111111111111111111111111111111111111112"
    print(f"\nBacktest mode -- {token}")

    try:
        raw = fetch_ohlc(token, chain=args.chain, interval="1H", limit=200)
    except Exception as e:
        print(f"[ERROR] Data fetch failed: {e}")
        return

    bars = []
    for c in raw:
        try:
            ts_val = c.get("timestamp", c.get("t", 0))
            if isinstance(ts_val, (int, float)) and ts_val > 1e10:
                ts = datetime.fromtimestamp(ts_val / 1000)
            else:
                ts = datetime.fromtimestamp(ts_val) if ts_val else datetime.now()
        except (ValueError, OSError, TypeError):
            ts = datetime.now()
        bars.append(Bar(
            timestamp=ts,
            open=float(c.get("open", c.get("o", 0))),
            high=float(c.get("high", c.get("h", 0))),
            low=float(c.get("low", c.get("l", 0))),
            close=float(c.get("close", c.get("c", 0))),
            volume=float(c.get("volume", c.get("v", 0))),
        ))

    if not bars:
        print("No kline data")
        return

    # Generate mock signals based on simple breakout
    signals = []
    for i in range(20, len(bars)):
        lookback = bars[i-20:i]
        avg_close = sum(b.close for b in lookback) / 20
        if bars[i].close > avg_close * 1.02:
            signals.append({
                "bar_index": i,
                "direction": "long",
                "confidence": 0.65,
                "symbol": token[:8],
            })

    engine = BacktestEngine(initial_capital=float(args.capital or 10000))
    engine.run_on_bars(bars, signals, token_address=token)
    print(engine.report())


def cmd_analyze(args):
    """Deep analyze a single token"""
    from strategies import MomentumBreakoutStrategy, WhaleTrackingStrategy, NewTokenSnipeStrategy

    token = args.token
    chain = args.chain or "solana"
    cfg = {"chain": chain}

    print(f"\nDeep Analysis: {token} (chain: {chain})")
    print("=" * 55)

    for name, Strat in [
        ("Momentum Breakout", MomentumBreakoutStrategy),
        ("Whale Tracking", WhaleTrackingStrategy),
        ("New Token Snipe", NewTokenSnipeStrategy),
    ]:
        print(f"\n--- {name} ---")
        try:
            strat = Strat(cfg)
            result = strat.analyze(token)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"  [ERROR] {e}")


def cmd_observe(args):
    """Historical data deep observation"""
    from data.fetcher import (
        fetch_ohlc, fetch_token_trades, fetch_token_info,
        fetch_token_price_info, fetch_token_holders,
    )

    token = args.token
    chain = args.chain or "solana"

    print(f"\n{'='*60}")
    print(f"  Historical Data Deep Observation: {token}")
    print(f"{'='*60}")

    # 1. Token basic info
    print("\n[1/4] Token Basic Info:")
    try:
        info = fetch_token_info(token, chain)
        _print_dict(info)
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 2. OHLC overview
    print("\n[2/4] K-line Data (latest 96 bars, 15m):")
    try:
        candles = fetch_ohlc(token, chain, interval="15m", limit=96)
        if candles:
            closes = [float(c.get("close", c.get("c", 0))) for c in candles]
            volumes = [float(c.get("volume", c.get("v", 0))) for c in candles]
            if closes:
                high = max(closes)
                low = min(closes)
                avg_vol = sum(volumes) / max(len(volumes), 1)

                if len(closes) >= 20:
                    ma20 = sum(closes[-20:]) / 20
                    ma50 = sum(closes[-min(50, len(closes)):]) / min(50, len(closes))
                    volatility = (max(closes[-20:]) - min(closes[-20:])) / max(ma20, 1e-10) * 100
                else:
                    ma20 = ma50 = volatility = 0

                print(f"   Current:     {closes[-1]:.8f}")
                print(f"   High:        {high:.8f}")
                print(f"   Low:         {low:.8f}")
                print(f"   MA20:        {ma20:.8f}")
                print(f"   MA50:        {ma50:.8f}")
                print(f"   Volatility:  {volatility:.1f}%")
                print(f"   Avg Volume:  ${avg_vol:,.0f}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 3. Recent trade flow
    print("\n[3/4] Recent Trade Flow (latest 30):")
    try:
        trades = fetch_token_trades(token, chain, limit=30)
        buys = sum(1 for t in trades if str(t.get("side", "")).lower() == "buy")
        sells = len(trades) - buys
        buy_vol = sum(float(t.get("amount_usd", t.get("amountUsd", t.get("amount", 0))))
                      for t in trades if str(t.get("side", "")).lower() == "buy")
        sell_vol = sum(float(t.get("amount_usd", t.get("amountUsd", t.get("amount", 0))))
                       for t in trades if str(t.get("side", "")).lower() == "sell")
        print(f"   Buys: {buys} | Sells: {sells}")
        print(f"   Buy Vol: ${buy_vol:,.0f} | Sell Vol: ${sell_vol:,.0f}")
        print(f"   Net Flow: ${buy_vol - sell_vol:+,.0f}")

        for t in trades[:5]:
            side = t.get("side", "?")
            price = t.get("price", 0)
            amount = t.get("amount_usd", t.get("amountUsd", t.get("amount", 0)))
            ts = t.get("timestamp", "")
            print(f"   {side:6s} ${float(amount):>8,.0f} @ {float(price):.8f}  {ts}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 4. Holder distribution
    print("\n[4/4] Holder Distribution:")
    try:
        holders = fetch_token_holders(token, chain, limit=20)
        items = holders if isinstance(holders, list) else holders.get("holders", holders.get("data", []))
        total_pct = 0
        for h in items[:10]:
            pct = float(h.get("percentage", h.get("pct", h.get("holdingPercent", 0))))
            total_pct += pct
            addr = h.get("address", h.get("holder", "?"))[:12]
            print(f"   {addr}... {pct:.2f}%")
        print(f"   Top-10 Concentration: {total_pct:.1f}%")
    except Exception as e:
        print(f"  [ERROR] {e}")


def _print_dict(data: dict, indent: int = 4):
    """Pretty print dictionary"""
    prefix = " " * indent
    for k, v in data.items():
        if isinstance(v, dict):
            print(f"{prefix}{k}:")
            _print_dict(v, indent + 2)
        elif isinstance(v, list):
            print(f"{prefix}{k}: [{len(v)} items]")
        else:
            print(f"{prefix}{k}: {v}")


# ═══════════════════════ main ═══════════════════════

def main():
    parser = argparse.ArgumentParser(description="H AI Quant Platform")
    sub = parser.add_subparsers(dest="cmd")

    # scan (default)
    p_scan = sub.add_parser("scan", help="Single scan mode")
    p_scan.add_argument("--execute", action="store_true", help="Execute trades")
    p_scan.add_argument("--capital", type=float, default=10000, help="Initial capital")

    # watch
    p_watch = sub.add_parser("watch", help="Continuous monitoring")
    p_watch.add_argument("--interval", type=int, default=60, help="Scan interval (s)")
    p_watch.add_argument("--capital", type=float, default=10000, help="Initial capital")
    p_watch.add_argument("--rounds", type=int, default=0, help="Rounds (0=infinite)")

    # backtest
    p_bt = sub.add_parser("backtest", help="Backtest mode")
    p_bt.add_argument("--token", type=str, help="Token address")
    p_bt.add_argument("--chain", type=str, default="solana")
    p_bt.add_argument("--capital", type=float, default=10000)

    # analyze
    p_an = sub.add_parser("analyze", help="Deep analysis")
    p_an.add_argument("--token", type=str, required=True, help="Token address")
    p_an.add_argument("--chain", type=str, default="solana")

    # observe
    p_ob = sub.add_parser("observe", help="Historical data observation")
    p_ob.add_argument("--token", type=str, required=True, help="Token address")
    p_ob.add_argument("--chain", type=str, default="solana")

    args = parser.parse_args()

    if args.cmd == "backtest":
        cmd_backtest(args)
        return

    if args.cmd == "analyze":
        cmd_analyze(args)
        return

    if args.cmd == "observe":
        cmd_observe(args)
        return

    # Default: scan / watch
    print("=" * 55)
    print("  H AI Quant Platform -- On-chain Signal Scan")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    cfg = load_config()
    strategies = init_strategies(cfg)

    if not strategies:
        print("[ERROR] No strategies enabled. Check config/settings.yaml")
        return

    wallet = SimulatedWallet(
        initial_usdc=float(getattr(args, 'capital', cfg.get("backtest", {}).get("initial_capital", 10000))),
        initial_sol=10.0,
    )

    if args.cmd == "watch":
        watch_loop(strategies, wallet,
                   interval=int(getattr(args, 'interval', 60)),
                   rounds=int(getattr(args, 'rounds', 0)))
        return

    # Single scan
    signals = scan_all(strategies)

    if not signals:
        print("\n[No signals this round]")
        wallet.print_summary()
        return

    # Generate report
    report = generate_signal_report(signals)
    print(f"\n=== Signal Summary ({len(signals)} total) ===")
    print(report.to_string(index=False))

    # Optional execution
    if hasattr(args, 'execute') and args.execute:
        print("\n--- Simulated Execution ---")
        execute_signals(wallet, signals)
        wallet.print_summary()


if __name__ == "__main__":
    main()
