"""
链上数据获取层 — 封装 onchainos CLI 调用
正确命令格式: onchainos <module> <subcommand> --address <ADDR> --chain <CHAIN>
"""

import subprocess
import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config.settings import DATA_DIR, CACHE_TTL_SECONDS


def _run(args: list[str], timeout: int = 60) -> dict:
    """执行 onchainos 命令，返回 JSON"""
    result = subprocess.run(
        ["onchainos"] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"onchainos error: {result.stderr.strip()}")
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw": stdout}


# ═══════════════════════════════════════════
# 价格与K线
# ═══════════════════════════════════════════

def fetch_price(token_address: str, chain: str = "solana") -> dict:
    """获取代币实时价格"""
    return _run(["market", "price", "--address", token_address, "--chain", chain])


def fetch_ohlc(token_address: str, chain: str = "solana",
               interval: str = "15m", limit: int = 96) -> list[dict]:
    """获取 K线数据. bar: 1m/5m/15m/1H/4H/1D, limit: max 299"""
    # onchainos uses --bar not --interval (capital H for hours)
    bar = interval.upper().replace("MIN", "m").replace("HR", "H")
    result = _run([
        "market", "kline", "--address", token_address, "--chain", chain,
        "--bar", bar, "--limit", str(limit),
    ])
    # onchainos returns {"data": [...]} or {"candles": [...]}
    if isinstance(result, list):
        return result
    return result.get("data", result.get("candles", result.get("kline", [])))


def fetch_multi_prices(token_addresses: list[str], chain: str = "solana") -> dict[str, dict]:
    """批量获取代币价格"""
    results = {}
    for addr in token_addresses:
        try:
            results[addr] = fetch_price(addr, chain)
            time.sleep(0.2)
        except Exception as e:
            results[addr] = {"error": str(e)}
    return results


# ═══════════════════════════════════════════
# 聪明钱 / 头部交易者
# ═══════════════════════════════════════════

def fetch_top_traders(token_address: str, chain: str = "solana",
                      limit: int = 20) -> dict:
    """获取头部交易者/聪明钱数据"""
    return _run(["token", "top-trader", "--address", token_address,
                 "--chain", chain, "--limit", str(limit)])


def fetch_signals(chain: str = "solana", limit: int = 20,
                  wallet_type: str = "1,3") -> dict:
    """获取聚合聪明钱买入信号
    wallet_type: 1=Smart Money, 2=KOL, 3=Whales
    """
    return _run(["signal", "list", "--chain", chain, "--limit", str(limit),
                 "--wallet-type", wallet_type])


def fetch_leaderboard(chain: str = "solana", sort_by: str = "1",
                      time_frame: str = "1", limit: int = 20) -> dict:
    """获取交易者排行榜
    sort_by: 1=PnL, 2=Win Rate, 3=Tx number, 4=Volume, 5=ROI
    time_frame: 1=1D, 2=3D, 3=7D, 4=1M, 5=3M
    """
    return _run(["leaderboard", "list", "--chain", chain,
                 "--time-frame", time_frame, "--sort-by", sort_by,
                 "--limit", str(limit)])


# ═══════════════════════════════════════════
# 代币深度信息
# ═══════════════════════════════════════════

def fetch_token_info(token_address: str, chain: str = "solana") -> dict:
    """获取代币基础信息"""
    return _run(["token", "info", "--address", token_address, "--chain", chain])


def fetch_token_advanced(token_address: str, chain: str = "solana") -> dict:
    """获取代币高级信息（开发者、捆绑、狙击手检测）"""
    return _run(["token", "advanced-info", "--address", token_address,
                 "--chain", chain])


def fetch_token_report(token_address: str, chain: str = "solana") -> dict:
    """复合报告: info + price-info + advanced-info + security scan"""
    return _run(["token", "report", "--address", token_address, "--chain", chain])


def fetch_token_holders(token_address: str, chain: str = "solana",
                        limit: int = 100) -> dict:
    """获取代币持仓分布"""
    return _run(["token", "holders", "--address", token_address, "--chain", chain,
                 "--limit", str(limit)])


def fetch_token_trades(token_address: str, chain: str = "solana",
                       limit: int = 50) -> list[dict]:
    """获取代币近期逐笔交易"""
    result = _run(["token", "trades", "--address", token_address, "--chain", chain,
                   "--limit", str(limit)])
    if isinstance(result, list):
        return result
    return result.get("data", result.get("trades", []))


def fetch_token_price_info(token_address: str, chain: str = "solana") -> dict:
    """获取代币详细价格信息（市值、流动性、24h变化）"""
    return _run(["token", "price-info", "--address", token_address, "--chain", chain])


# ═══════════════════════════════════════════
# 新盘 / 热门代币
# ═══════════════════════════════════════════

def fetch_hot_tokens(chain: str = "solana", limit: int = 50,
                     ranking_type: str = "4") -> list[dict]:
    """获取热门代币榜单. ranking_type: 4=Trending, 5=Xmentioned"""
    result = _run(["token", "hot-tokens", "--chain", chain,
                   "--limit", str(limit), "--ranking-type", ranking_type])
    if isinstance(result, list):
        return result
    return result.get("data", result.get("tokens", []))


def fetch_trending(chain: str = "solana", limit: int = 20) -> list[dict]:
    """获取热门代币 (Trending 排行)"""
    return fetch_hot_tokens(chain, limit, ranking_type="4")


def fetch_new_tokens(chain: str = "solana", limit: int = 50) -> list[dict]:
    """获取最新代币 (按创建时间排序)"""
    result = _run(["token", "hot-tokens", "--chain", chain,
                   "--limit", str(limit), "--rank-by", "8"])  # 8=created time
    if isinstance(result, list):
        return result
    return result.get("data", result.get("tokens", []))


def fetch_meme_tokens(chain: str = "solana", limit: int = 50) -> list[dict]:
    """获取 Meme/Pump 代币列表"""
    result = _run(["memepump", "tokens", "--chain", chain, "--limit", str(limit)])
    if isinstance(result, list):
        return result
    return result.get("data", result.get("tokens", []))


# ═══════════════════════════════════════════
# 缓存层
# ═══════════════════════════════════════════

class DataCache:
    """文件缓存"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (DATA_DIR / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, prefix: str, *args) -> str:
        return f"{prefix}_{'_'.join(str(a) for a in args)}.json"

    def get(self, prefix: str, *args, ttl: int = None) -> Optional[dict]:
        ttl = ttl or CACHE_TTL_SECONDS
        key = self._key(prefix, *args)
        path = self.cache_dir / key
        if not path.exists():
            return None
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(seconds=ttl):
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, prefix: str, *args, data: dict):
        key = self._key(prefix, *args)
        path = self.cache_dir / key
        path.write_text(json.dumps(data, ensure_ascii=False, default=str),
                        encoding="utf-8")

    def clear_old(self, max_age_seconds: int = 3600):
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        for f in self.cache_dir.glob("*.json"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()


cache = DataCache()


def cached_fetch(prefix: str, fetcher, *args, ttl: int = None):
    """带缓存的通用获取函数"""
    cached = cache.get(prefix, *args, ttl=ttl)
    if cached is not None:
        return cached
    data = fetcher(*args)
    cache.set(prefix, *args, data=data)
    return data
