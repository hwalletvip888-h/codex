"""
H AI 量化平台 全局配置
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# onchainos 配置
ONCHAINOS_BIN = "onchainos"

# 交易配置
MAX_POSITION_PCT = 0.2        # 单笔最大仓位 20%
DEFAULT_SLIPPAGE_BPS = 100    # 默认滑点 1%
GAS_LIMIT_MULTIPLIER = 1.2    # Gas 上限系数

# 数据缓存
CACHE_TTL_SECONDS = 300       # 缓存有效期 5 分钟

# ═══════════════════════════════════════
# YAML 配置加载
# ═══════════════════════════════════════

def load_yaml_config(path: str = None) -> dict:
    """加载 YAML 配置文件"""
    import yaml
    if path is None:
        path = PROJECT_ROOT / "config" / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
