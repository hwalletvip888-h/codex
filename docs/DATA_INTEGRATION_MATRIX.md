# Data Integration Matrix

## 项目目标

本项目主攻 Solana 链 meme 币策略。数据对接优先级不是“谁数据多”，而是谁更适合发现新币、过滤风险、跟踪聪明钱、生成交易计划和复盘。

## 结论

第一阶段优先接 OKX Onchain OS。

原因：

- 直接覆盖 Solana、meme pump / trenches、新币、token 画像、持仓簇、聪明钱、KOL、鲸鱼、价格、K线、钱包 PnL、安全扫描和 swap quote。
- 对 SOL meme 策略最关键的“发现 + 风控 + 信号”都在 OKX 侧。
- Hummingbot API 更适合作为后续交易机器人编排和复盘层，不适合作为第一阶段的新币发现主数据源。

## OKX Onchain OS 可对接数据

### 1. Meme 新币发现

来源：`okx-dex-trenches`

可接数据：

- 支持链和 launchpad 协议
- Solana meme 新币列表
- NEW / MIGRATING / MIGRATED 阶段
- Token address / mint address
- 创建时间
- 市值
- bonding curve 进度
- Top 10 持仓集中度
- token 详情
- dev 声誉和历史
- dev 持仓
- 同 dev 相似 token
- bundle / sniper 分析
- aped wallets / 同车钱包

用途：

- 观察池入口
- 新币扫描
- dev 黑名单
- bundle / sniper 风险拦截
- 早期同车钱包追踪

第一阶段优先级：P0

### 2. Token 画像和池子数据

来源：`okx-dex-token`

可接数据：

- token 搜索
- token 元数据：name、symbol、decimals、logo
- price-info：价格、市值、流动性、成交量、24h 变化
- holder distribution：Top 100 持有人、KOL / whale / smart money 标签过滤
- top liquidity pools：Top 5 池子、流动性 USD、池内 token 数量、LP fee
- hot tokens：热门 / trending / X mentions
- advanced-info：风险控制等级、创建者、dev 统计、持仓集中度
- top-trader：盈利地址和顶级交易者
- trades：逐笔 DEX 交易历史
- cluster-overview：持仓簇集中度、rug pull 风险、新钱包比例
- cluster-top-holders：Top 10/50/100 持有人概览、平均 PnL、成本、趋势
- cluster-list：Top 300 持有人簇和地址明细

用途：

- token 标准画像表
- 流动性过滤
- 持仓集中度过滤
- 聪明钱 / 鲸鱼持仓确认
- 顶级交易者反查
- 交易行为复盘

第一阶段优先级：P0

### 3. 行情、K线和钱包 PnL

来源：`okx-dex-market`

可接数据：

- 单 token 实时价格
- 批量 token 价格
- K-line / OHLC 蜡烛图
- index price
- 支持 PnL 的链
- 钱包 PnL overview：胜率、已实现 PnL、Top tokens
- 钱包 DEX 历史
- 最近 PnL
- 单 token 已实现 / 未实现 PnL

用途：

- 入场前价格确认
- 观察池价格刷新
- 策略信号里的动量和回撤
- 跟踪聪明钱钱包收益质量
- 自己钱包的交易复盘

第一阶段优先级：P0

### 4. 聪明钱、KOL、鲸鱼和排行榜

来源：`okx-dex-signal`

可接数据：

- smart money / KOL / whale 实际交易流水
- 自定义钱包地址交易追踪
- 买入方向聚合信号
- 支持 signal 的链
- 信号钱包类型：Smart Money、KOL、Whale
- 交易金额 USD
- 触发钱包数量
- 信号时价格
- sold ratio：已卖出比例
- leaderboard：按 PnL、胜率、交易次数、交易量、ROI 排名
- 钱包类型：sniper、dev、fresh、pump、smartMoney、influencer

用途：

- SOL meme 早期买盘确认
- 钱包白名单
- 钱包黑名单
- 跟踪聪明钱是否还持有
- 找高胜率 meme 钱包

第一阶段优先级：P0

### 5. 安全扫描和风险拦截

来源：`okx-security`

可接数据：

- token risk scan
- overall `riskLevel`：CRITICAL、HIGH、MEDIUM、LOW
- honeypot / low liquidity / fake liquidity / not open source 等标签
- Solana asset edit authority 相关风险
- DApp / URL phishing scan
- transaction pre-execution scan：EVM + Solana
- signature scan：EVM
- approval / Permit2 授权查询：EVM

用途：

- 买入前硬拦截
- 高风险 token 进观察池但不进交易计划
- 交易前模拟和风险提示
- DApp / URL 安全检查

第一阶段优先级：P0

### 6. 实时流

来源：`okx-dex-ws`

可接数据：

- Solana 新 meme token launch 实时流
- meme token metric update：市值、成交量、bonding curve
- token price
- token price-info
- trades 逐笔成交
- K-line candles
- smart money / KOL tracker
- 自定义钱包 tracker
- buy signal alerts

用途：

- 实时观察池
- 新币触发器
- 价格 / 成交流更新
- 钱包异动提醒

第一阶段优先级：P1，先用 CLI / REST，后面再做 WS 常驻进程。

### 7. 组合和余额

来源：`okx-wallet-portfolio`

可接数据：

- 支持余额查询的链
- 钱包总资产价值
- 所有 token balances
- 指定 token balances
- tokenContractAddress
- token amount
- USD value
- 风险 token 排除选项：ETH / BSC / SOL / BASE

用途：

- 买入前检查 SOL / USDC 余额
- 持仓表
- 止盈止损和复盘
- 低价值 dust 过滤

第一阶段优先级：P1

### 8. Swap 和交易广播

来源：`okx-dex-swap`、`okx-onchain-gateway`

可接数据 / 能力：

- 支持链
- Solana 原生 SOL 地址：`11111111111111111111111111111111`
- swap liquidity sources
- swap quote
- expected output
- gas / fee
- price impact
- route path
- isHoneyPot
- taxRate
- unsigned tx data
- one-shot execute
- gas price
- gas limit
- transaction simulation
- signed tx broadcast
- order tracking
- Solana Jito tips / MEV protection

用途：

- 第一阶段只接 quote，不直接 execute。
- 生成交易草案。
- 人工确认后再考虑广播。
- 后续做自动化时作为执行层。

第一阶段优先级：P2

## Hummingbot API 可对接数据

### 1. 账户和凭证

Router：`/accounts`

可接数据 / 能力：

- account namespace
- exchange connector credentials
- Gateway wallets
- 按 chain / address 删除 Gateway wallet

用途：

- 管理 CEX / DEX 执行账户
- 后续多账户机器人编排

对 SOL meme 第一阶段优先级：P3

### 2. Connector 信息

Router：`/connectors`

可接数据：

- 可用 connector names
- connector config map
- trading rules
- supported order types

用途：

- 判断某交易所 / connector 是否支持目标 pair
- 下单前校验最小下单量、精度、订单类型

对 SOL meme 第一阶段优先级：P3

### 3. Portfolio

Router：`/portfolio`

可接数据：

- 当前余额和估值
- 历史 portfolio snapshot
- token-level distribution
- account-level allocation

用途：

- 跨账户资产汇总
- 策略资金曲线
- 风险敞口

对 SOL meme 第一阶段优先级：P2

### 4. Trading

Router：`/trading`

可接数据 / 能力：

- 创建订单
- 取消订单
- 查询永续仓位
- active orders
- historical orders
- historical trades / fills
- position mode
- leverage
- funding payments

用途：

- 后续 CEX / perp 对冲
- 机器人执行和成交记录
- 交易复盘

对 SOL meme 第一阶段优先级：P3

### 5. Market Data

Router：`/market-data`

可接数据：

- live / cached candles
- historical OHLCV candles
- active feed subscriptions
- market-data settings
- candle-supported connectors
- latest prices
- funding info
- order book snapshot
- price-for-volume

用途：

- CEX 行情补充
- OHLCV 回测
- 滑点估算
- 对冲腿行情

对 SOL meme 第一阶段优先级：P2

### 6. Rate Oracle

Router：`/rate-oracle`

可接数据：

- oracle sources
- oracle config
- pair rates
- cached rate
- fresh async rate
- all cached prices

用途：

- 稳定计价
- USD 估值
- 跨资产汇率换算

对 SOL meme 第一阶段优先级：P2

### 7. Bot Orchestration / Executors

Routers：`/bot-orchestration`、`/executors`

可接数据 / 能力：

- 所有 bot 状态
- 单 bot 状态
- bot 历史和 performance
- start / stop bot
- bot runs
- executor 创建、搜索、详情、日志、performance、positions

用途：

- 后续策略机器人化
- 多 bot 监控
- 执行器复盘

对 SOL meme 第一阶段优先级：P3

### 8. Scripts / Controllers / Backtesting

Routers：`/scripts`、`/controllers`、`/backtesting`

可接数据 / 能力：

- 列出脚本和配置
- 读取 / 创建 / 更新脚本
- 读取 / 创建 / 更新 controller
- 获取配置模板
- 运行同步回测
- 返回 executors、processed_data、results

用途：

- 策略模板化
- 回测
- 后续把成熟策略搬进机器人框架

对 SOL meme 第一阶段优先级：P3

### 9. Gateway / Gateway Proxy

Routers：`/gateway`、`/gateway-proxy`

可接数据 / 能力：

- Gateway 状态、启动、停止、重启、日志、配置
- connectors
- tokens
- pools
- wallets
- DEX swap quote
- DEX swap execute
- CLMM quote
- CLMM pools
- CLMM positions
- add / remove liquidity
- collect fees
- CLMM balances
- raw Gateway endpoint proxy

用途：

- DEX 执行基础设施
- CLMM 流动性策略
- 后续如果做做市或池子策略可用

对 SOL meme 第一阶段优先级：P3

### 10. Archived Bot Analytics

Router：`/archived-bots`

可接数据：

- archived bot databases
- archive status
- summary metrics
- performance analysis
- archived trades
- archived orders
- archived controllers
- archived positions

用途：

- 机器人运行后复盘
- 历史成交和订单分析

对 SOL meme 第一阶段优先级：P3

## 建议数据表

### `meme_tokens`

- chain
- chain_index
- token_address
- mint_address
- symbol
- name
- protocol
- stage
- created_at
- market_cap_usd
- liquidity_usd
- volume_24h_usd
- price_usd
- price_change_24h
- bonding_percent
- top10_holders_percent
- holder_count
- dev_wallet
- dev_rug_count
- bundle_score
- sniper_score
- risk_level
- can_sell
- status
- first_seen_at
- last_checked_at

### `meme_signals`

- token_address
- chain
- signal_source
- wallet_type
- wallet_address
- amount_usd
- trigger_wallet_count
- sold_ratio_percent
- price_at_signal
- market_cap_at_signal
- tx_hash
- signal_at

### `wallet_profiles`

- wallet_address
- chain
- wallet_type
- pnl
- win_rate
- tx_count
- volume_usd
- roi
- tags
- first_seen_at
- last_seen_at

### `risk_checks`

- token_address
- chain
- risk_level
- triggered_labels
- is_honeypot
- is_low_liquidity
- is_fake_liquidity
- top_holder_risk
- dev_risk
- bundle_risk
- sniper_risk
- scan_status
- checked_at

### `trade_plans`

- token_address
- chain
- side
- planned_size_sol
- max_loss_usd
- entry_reason
- invalid_condition
- stop_loss
- take_profit_levels
- quote_expected_output
- quote_price_impact
- quote_route
- requires_manual_confirm
- status
- created_at

## 第一阶段对接顺序

1. OKX trenches：Solana meme 新币扫描。
2. OKX token：补 token 画像、流动性、持仓、交易、cluster。
3. OKX security：买入前风险硬拦截。
4. OKX signal：聪明钱 / KOL / 鲸鱼信号和 leaderboard。
5. OKX market：价格、K线、钱包 PnL。
6. OKX swap quote：只生成交易草案，不自动执行。
7. Hummingbot Gateway：等我们有稳定筛选规则后，先接 Jupiter / Raydium / Meteora 的 quote-only。
8. Hummingbot API：等 quote-only 和人工小额执行稳定后，再接 portfolio / market-data / backtesting / bot orchestration。

## Sources

- OKX Onchain OS skills repository: https://github.com/okx/onchainos-skills
- OKX Onchain OS skills docs: https://web3.okx.com/onchainos/dev-docs/market/market-ai-tools-skills
- Hummingbot API docs: https://hummingbot.org/hummingbot-api/
- Hummingbot API routers: https://hummingbot.org/hummingbot-api/routers/
