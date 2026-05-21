---
name: h-quant-trader
description: H AI量化交易机器人 — 基于链上聪明钱信号的自动化交易策略。扫描鲸鱼/聪明钱买入信号，模拟买入，自动止盈止损，持久化日志。触发词：量化交易、自动交易、策略扫描、模拟交易、止盈止损、信号扫描、交易机器人、量化策略、meme交易
---

# H AI 量化交易策略

## 策略概述

基于 `onchainos` CLI 实时链上数据的自动化交易策略系统。核心思路：追踪聪明钱(Smart Money)/鲸鱼(Whale)的买入行为，跟随大户资金流向进行交易。

## 核心策略信号

### 信号来源: Whale Tracking (鲸鱼追踪)

调用 `onchainos signal list --chain solana` 获取实时聪明钱聚合信号。

**信号质量分层 (经26h+实盘验证):**

| 信号类型 | Wallet Type | 质量 | 表现 |
|----------|-------------|------|------|
| 6+ Whale | 3 | 最高 | WR26 +102%, AOC +108% |
| 7-9 SmartMoney | 1 | 高 | daedalus +60%, HEDGY +66% |
| 5 SmartMoney | 1 | 中 | RKC +30%, DEGEN +15% |
| 4 SmartMoney | 1 | 低 | SACKS -23%, PAC -22% |
| 3 SmartMoney | 1 | 最低 | 多数首轮崩盘 |

### 信号筛选规则

1. `triggerWalletCount >= 2` — 至少2个地址同时买入
2. 去重: 同代币地址只取一次
3. 黑名单过滤: 同地址触发2次止损 → 永久拉黑
4. 冷却机制: TP/SL后2轮内不复买同代币
5. 按`confidence`降序取Top 5

## 风控参数

| 参数 | 数值 | 说明 |
|------|------|------|
| STOP_LOSS | -20% | 硬止损，立即市价卖出 |
| TAKE_PROFIT | 45% | 硬止盈（从50%下调，避免+49%→反转） |
| MAX_POSITIONS | 5/轮 | 每轮最多买入5个 |
| POSITION_SIZE | $400 | 单笔仓位 |
| COOLDOWN_ROUNDS | 2 | TP/SL后冷却轮次 |
| MAX_SL_BEFORE_BAN | 2 | 触发N次止损后永久拉黑 |

## 核心经验 (30h+ 模拟总结)

### 1. 止盈是生命线
- ENHA 曾 +65%(+$247) 未止盈 → -20%止损 -$76
- PHOENIX +49.4% 距TP差0.6% → -35%止损 -$830
- 设止盈且触发的全部大赚 (WR26/HEDGY/AOC/NYAN)

### 2. 30-60分钟是最佳止盈窗口
- 所有翻倍币均在1h内达峰
- 持仓超过2h的币几乎全部衰减

### 3. 黑名单是必须的
- BOB被买6次归零6次，累计吞噬$1,875
- Flork被买2次归零2次
- 无黑名单时年化从+25%降至+6%

### 4. 避免复买陷阱
- daedalus TP +$966 → 复买 → SL -$111
- NYAN TP +$655 → 复买 → SL -$388
- TP后的代币有极高概率在下一轮崩盘

### 5. 鲸鱼质量 > 数量
- 6 Whale (WR26) 翻倍 vs 5 SmartMoney (ELMO) 归零
- 地址类型比数量更关键

### 6. 老币稳定性 > 新币
- 新币首轮失败率 ~60%
- 跨轮次存活的老币 (RKC, DEGEN, Fartcoin) 更可靠

### 7. 夜间/凌晨交易风险极高
- 凌晨3-5点新币几乎全部崩盘
- 低流动性时段信号噪声比急剧恶化

## 执行命令

```bash
# 扫描信号 (不执行)
python scripts/auto_trader.py scan

# 扫描 + 买入 Top 5
python scripts/auto_trader.py trade

# 检查持仓 + 自动止盈止损
python scripts/auto_trader.py check

# 生成完整报告
python scripts/auto_trader.py report

# 更新记忆文件
python scripts/auto_trader.py memory
```

## 持久化文件

| 文件 | 内容 |
|------|------|
| `data/trade_log.json` | 完整交易日志 (入场/出场/快照/观察) |
| `data/auto_state.pkl` | 钱包状态 (持仓/余额/交易历史) |
| `memory/trade_memory.md` | 每30分钟自动更新的永久记忆 |

## 实盘接入

实盘交易通过 `onchainos swap execute` 接入 Agent Wallet:

```bash
# 扫描信号获取代币地址
python -c "from strategies import WhaleTrackingStrategy; ..."

# 查地址
onchainos token search --query <SYMBOL> --chains solana

# 买入
onchainos swap execute --from sol --to <CA> --readable-amount <AMT> --chain solana --wallet <ADDR>
```

## 模块架构

```
strategies/
  whale_tracking.py    # 鲸鱼追踪策略 (主力)
  momentum_breakout.py # 动量突破策略 (辅助)
  new_token_snipe.py   # 新币狙击策略 (实验)
  base.py              # Signal + BaseStrategy 基类
scripts/
  auto_trader.py       # 自动交易机器人
  sim_trade.py         # 旧模拟盘 (被动持有对比)
data/
  trade_log.json       # 交易日志持久库
  auto_state.pkl       # 钱包状态
analysis/
  history.py           # 历史数据深度分析
  reporter.py          # 信号报告生成
paper_trade/
  wallet.py            # 模拟钱包
backtest/
  engine.py            # 回测引擎
```
