"""
H AI量化平台 — 数据模块
"""
from data.fetcher import (
    fetch_price, fetch_ohlc, fetch_multi_prices,
    fetch_top_traders, fetch_signals, fetch_leaderboard,
    fetch_token_info, fetch_token_advanced, fetch_token_report,
    fetch_token_holders, fetch_token_trades, fetch_token_price_info,
    fetch_new_tokens, fetch_trending, fetch_hot_tokens, fetch_meme_tokens,
    DataCache, cache, cached_fetch,
)
