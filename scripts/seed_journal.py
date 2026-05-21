"""重建完整模拟日志 — 包含全部历史记录"""
import sys, json
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import PROJECT_ROOT

JOURNAL_FILE = PROJECT_ROOT / "data" / "sim_journal.json"

journal = {
    "updated_at": datetime.now().isoformat(),
    "entries": [
        {"timestamp": "2026-05-20T10:01:29", "event": "ENTRY", "token_symbol": "ENHA",
         "token_address": "AGWmh5GfPKqEtWoXXpo43p3SGr4CKxB5XYfEvBjMpump", "price": 0.00020209,
         "details": {"cost": 380, "confidence": 0.95, "reason": "7 SmartMoney wallets, total $438"}},
        {"timestamp": "2026-05-20T10:01:29", "event": "ENTRY", "token_symbol": "RKC",
         "token_address": "7HgfXftRBBqsYtAEYcqjGLQrNJLL6Tww9ek4rE3Apump", "price": 0.00518376,
         "details": {"cost": 380, "confidence": 0.95, "reason": "5 SmartMoney wallets, total $913"}},
        {"timestamp": "2026-05-20T10:01:30", "event": "ENTRY", "token_symbol": "WR26",
         "token_address": "2DK6WxzW9UT5mDr3rivN8oeiUmWVkGucaXgAKc4Wpump", "price": 0.000351,
         "details": {"cost": 380, "confidence": 0.95, "reason": "6 Whale wallets, total $8,517"}},
        {"timestamp": "2026-05-20T10:01:30", "event": "ENTRY", "token_symbol": "ELMO",
         "token_address": "E4q2QyUe7nRTac7HiEmxp26KgnPNAieKfCaZo8USpump", "price": 0.00004060,
         "details": {"cost": 380, "confidence": 0.95, "reason": "5 SmartMoney wallets, total $972"}},
        {"timestamp": "2026-05-20T10:01:30", "event": "ENTRY", "token_symbol": "SACKS",
         "token_address": "G1cEcV5JrKEKBnjauXAPwfs7ak4LQGEZJoLTKvvEpump", "price": 0.00005780,
         "details": {"cost": 352, "confidence": 0.88, "reason": "4 SmartMoney wallets, total $166"}},
        {"timestamp": "2026-05-20T10:35:00", "event": "EXIT", "token_symbol": "ELMO",
         "token_address": "E4q2QyUe7nRTac7HiEmxp26KgnPNAieKfCaZo8USpump", "price": 0.00000586,
         "details": {"exit_reason": "STOP_LOSS", "change_pct": -85.6, "pnl_usd": -325.98}},
        {"timestamp": "2026-05-20T10:49:06", "event": "EXIT", "token_symbol": "WR26",
         "token_address": "2DK6WxzW9UT5mDr3rivN8oeiUmWVkGucaXgAKc4Wpump", "price": 0.00071076,
         "details": {"exit_reason": "TAKE_PROFIT", "change_pct": 102.5, "pnl_usd": 389.48}},
    ],
    "observations": [
        {"timestamp": "2026-05-20T10:02", "note": "ENTRY: 5 positions opened. ELMO already weak (-86%). WR26 strong with 6 whale backing."},
        {"timestamp": "2026-05-20T10:34", "note": "30min: WR26 +101% doubled. ELMO -86% stopped out. ENHA from +65% to +33%. Meme decay pattern emerging."},
        {"timestamp": "2026-05-20T10:49", "note": "WR26 auto TP at +102.5% (+$389). ELMO SL -85.6% (-$326). Closed PnL: +$63 net. 3 positions remain."},
        {"timestamp": "2026-05-20T11:04", "note": "ENHA +20%, RKC +2%, SACKS +8%. All drifting sideways. Equity $10,176."},
        {"timestamp": "2026-05-20T11:14", "note": "ENHA rebounded to +28%. RKC first time negative -0.2%. SACKS fading to +3%. Equity $10,184."},
        {"timestamp": "2026-05-20T11:24", "note": "ENHA +26.5%, RKC +1.2%, SACKS +2.3%. Meme momentum exhausted after 1.5h. Equity $10,181."},
        {"timestamp": "2026-05-20T11:34", "note": "All 3 declining: ENHA +18.5%, RKC +2.2%, SACKS +1.6%. PnL eroded $33 in 20min. Equity $10,152."},
        {"timestamp": "2026-05-20T11:44", "note": "Bounce-back! RKC +8.3%, SACKS +8.7%, ENHA +20.8%. Second wind. Equity $10,209."},
        {"timestamp": "2026-05-20T11:54", "note": "Rotation: RKC +11.3% sole riser. ENHA +13.7%, SACKS -0.2%. Meme liquidity rotating. Equity $10,161."},
        {"timestamp": "2026-05-20T12:04", "note": "Broad rally! SACKS +11.6% (from -0.2%!), ENHA +20.8%, RKC +11.4%. Third buying wave. Equity $10,230."},
        {"timestamp": "2026-05-20T12:14", "note": "Wave 4 peak: RKC +16.1%, SACKS +19%, ENHA +22.3%. Equity $10,280 — session high. All ATHs."},
        {"timestamp": "2026-05-20T12:34", "note": "Flash crash: SACKS from +19% to +1.8% (-$61!). ENHA +16.7%, RKC +11.4%. Classic distribution. Equity $10,180."},
        {"timestamp": "2026-05-20T12:44", "note": "Stable: RKC +12.7% outperformer, ENHA +17.9%, SACKS +1.9%. RKC shows relative strength. Equity $10,190."},
        {"timestamp": "2026-05-20T12:54", "note": "Broad weakness: SACKS -6.2% (mirroring ELMO bleed pattern), RKC +9.9%, ENHA +17.9%. 3h fatigue. Equity $10,152."},
        {"timestamp": "2026-05-20T13:04", "note": "RKC +11.8% rebounded, ENHA +15% fading, SACKS -5.8%. 3.5h hold, meme decaying ~2-3%/hour. Equity $10,149."},
        {"timestamp": "2026-05-20T13:14", "note": "Mild bounce: RKC +15.3%, ENHA +15.8%, SACKS -4.3%. 4h sim: closed +$63, open +$103, combined +$166. Equity $10,171."},
        {"timestamp": "2026-05-20T13:24", "note": "ENHA +20.3%, RKC +13.8%, SACKS +1.9% back to positive. All green. Wave 5 mini-rally. Equity $10,204."},
        {"timestamp": "2026-05-20T13:34", "note": "RKC +15.4% takes lead. ENHA +13.9%, SACKS -0.7% flipped negative again. Equity $10,177."},
        {"timestamp": "2026-05-20T13:44", "note": "RKC +23.5% NEW HIGH! ENHA +17.7%, SACKS -2.7%. RKC single-handedly carrying portfolio. Equity $10,215."},
        {"timestamp": "2026-05-20T13:54", "note": "RKC +21.3% cooling, ENHA +14.4%, SACKS -5.6% deepening. RKC remains MVP. Equity $10,183."},
        {"timestamp": "2026-05-20T14:04", "note": "RKC +20.4% steady, ENHA +12.1% slipping, SACKS -5.6%. 5h fatigue. Equity $10,171."},
        {"timestamp": "2026-05-20T14:14", "note": "RKC +23.8% near ATH! SACKS +3.7% surprise bounce (from -5.6%). ENHA +10.9% continues slide. Equity $10,212."},
    ],
    "snapshots": [
        {"timestamp": "2026-05-20T10:02", "equity": 10336, "unrealized_pnl": 331,
         "positions": [{"symbol": "ENHA", "change_pct": 65.0, "pnl": 247}, {"symbol": "RKC", "change_pct": 5.2, "pnl": 20},
                       {"symbol": "WR26", "change_pct": 88.2, "pnl": 335}, {"symbol": "ELMO", "change_pct": -86.0, "pnl": -327},
                       {"symbol": "SACKS", "change_pct": 15.8, "pnl": 56}]},
        {"timestamp": "2026-05-20T10:34", "equity": 10218, "unrealized_pnl": 212,
         "positions": [{"symbol": "ENHA", "change_pct": 33.0, "pnl": 125}, {"symbol": "RKC", "change_pct": 4.9, "pnl": 19},
                       {"symbol": "WR26", "change_pct": 101.4, "pnl": 385}, {"symbol": "ELMO", "change_pct": -85.8, "pnl": -326},
                       {"symbol": "SACKS", "change_pct": 2.6, "pnl": 9}]},
        {"timestamp": "2026-05-20T10:49", "equity": 10184, "unrealized_pnl": 506,
         "positions": [{"symbol": "ENHA", "change_pct": 20.9, "pnl": 79}, {"symbol": "RKC", "change_pct": 3.0, "pnl": 11},
                       {"symbol": "SACKS", "change_pct": 7.2, "pnl": 25}]},
        {"timestamp": "2026-05-20T11:04", "equity": 10176, "unrealized_pnl": 108,
         "positions": [{"symbol": "ENHA", "change_pct": 19.6, "pnl": 74}, {"symbol": "RKC", "change_pct": 1.7, "pnl": 6},
                       {"symbol": "SACKS", "change_pct": 7.8, "pnl": 28}]},
        {"timestamp": "2026-05-20T11:24", "equity": 10181, "unrealized_pnl": 113,
         "positions": [{"symbol": "ENHA", "change_pct": 26.5, "pnl": 101}, {"symbol": "RKC", "change_pct": 1.2, "pnl": 4},
                       {"symbol": "SACKS", "change_pct": 2.3, "pnl": 8}]},
        {"timestamp": "2026-05-20T12:14", "equity": 10280, "unrealized_pnl": 213,
         "positions": [{"symbol": "ENHA", "change_pct": 22.3, "pnl": 85}, {"symbol": "RKC", "change_pct": 16.1, "pnl": 61},
                       {"symbol": "SACKS", "change_pct": 19.0, "pnl": 67}]},
        {"timestamp": "2026-05-20T12:34", "equity": 10180, "unrealized_pnl": 85,
         "positions": [{"symbol": "ENHA", "change_pct": 16.7, "pnl": 63}, {"symbol": "RKC", "change_pct": 11.4, "pnl": 43},
                       {"symbol": "SACKS", "change_pct": 1.8, "pnl": 6}]},
        {"timestamp": "2026-05-20T13:44", "equity": 10215, "unrealized_pnl": 147,
         "positions": [{"symbol": "ENHA", "change_pct": 17.7, "pnl": 67}, {"symbol": "RKC", "change_pct": 23.5, "pnl": 89},
                       {"symbol": "SACKS", "change_pct": -2.7, "pnl": -10}]},
        {"timestamp": "2026-05-20T14:14", "equity": 10212, "unrealized_pnl": 145,
         "positions": [{"symbol": "ENHA", "change_pct": 10.9, "pnl": 42}, {"symbol": "RKC", "change_pct": 23.8, "pnl": 90},
                       {"symbol": "SACKS", "change_pct": 3.7, "pnl": 13}]},
    ]
}

JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
    json.dump(journal, f, ensure_ascii=False, indent=2, default=str)

print(f"[OK] Full journal rebuilt: {len(journal['entries'])} entries, "
      f"{len(journal['observations'])} observations, {len(journal['snapshots'])} snapshots")
