# Hummingbot Execution Plan

## 定位

Hummingbot 不作为当前 Solana meme 监控面板的数据源。当前数据源仍然是 OKX Onchain OS。

Hummingbot 的定位是第二阶段执行层：

- 报价
- 模拟
- 小额人工确认交易
- 后续机器人管理
- 成交记录和复盘

## 当前阶段不接真实执行

当前只做：

- 未毕业币监控
- 刚毕业币追踪
- 风险标签
- 观察 / 重点看承接 / 跳过
- 交易草案

当前不做：

- 不保存私钥
- 不自动广播交易
- 不自动买入刚毕业 token
- 不自动追高
- 不把 Hummingbot 接成常驻交易机器人

## 可用组件

### Hummingbot Client

仓库：https://github.com/hummingbot/hummingbot

用途：

- 运行交易策略脚本
- 管理单个或少量机器人
- 本地运行，适合策略成熟后的执行测试

对本项目的价值：

- 后续可以写一个脚本读取候选 token 队列
- 只对通过 OKX 风险过滤的 token 请求报价
- 真实下单必须人工确认

### Hummingbot Gateway

仓库：https://github.com/hummingbot/gateway

用途：

- Solana DEX 执行中间层
- 钱包余额
- token 查询
- swap quote
- swap execute
- 交易状态轮询

对本项目最有用的连接器：

- Jupiter：Solana 聚合路由
- Raydium：AMM / CLMM
- Meteora：CLMM

第一步只使用：

- 余额查询
- swap quote
- 路由和价格影响检查

暂不使用：

- execute swap
- 钱包导入
- 自动签名

### Hummingbot API

仓库：https://github.com/hummingbot/hummingbot-api

用途：

- 多机器人管理
- REST API
- Swagger UI
- PostgreSQL 记录
- EMQX 实时消息
- MCP 接入

对本项目的价值：

- 等策略稳定后，用于管理多个执行机器人
- 记录成交、订单、策略运行、组合表现
- 给 AI 助手提供受控的交易操作接口

## 推荐接入顺序

### 阶段 1：只接 OKX 数据

状态：当前正在做。

数据流：

```text
OKX Onchain OS
  -> memepump NEW / MIGRATING / MIGRATED
  -> docs/data/meme.json
  -> GitHub Pages 面板
```

输出：

- 未毕业观察池
- 刚毕业追踪池
- 风险初筛
- 重点看承接名单

### 阶段 2：接 Hummingbot Gateway 报价

触发条件：

- token 处于刚毕业或临近毕业
- 1 小时成交量足够
- Top 10 持仓不过度集中
- sniper / bundler 未触发硬拦截
- OKX 安全扫描不是高危

数据流：

```text
docs/data/meme.json
  -> 候选 token
  -> Hummingbot Gateway Jupiter quote
  -> 价格影响 / 滑点 / 路由
  -> 交易草案
```

输出：

- 可买入金额建议
- 预估收到数量
- 价格影响
- 路由
- 最大滑点
- 是否需要人工确认

### 阶段 3：人工确认小额执行

前置条件：

- 完成 OKX token 安全扫描
- 完成 Hummingbot / Gateway 报价
- 明确止损和止盈
- 明确最大亏损
- 人工确认钱包、金额、滑点、token 地址

执行原则：

- 先小额
- 每次只执行一个 token
- 成交后立刻记录交易哈希
- 自动复盘，不自动加仓

### 阶段 4：Hummingbot API 编排

只有在阶段 3 稳定后再做。

用途：

- 多 bot 管理
- 历史订单
- 成交记录
- 策略 PnL
- 组合监控
- MCP 受控操作

## 风险闸门

任何一个条件触发，禁止执行：

- token 地址不明确
- 无法卖出或卖出报价失败
- Top 10 持仓过高
- sniper 过高
- bundler 过高
- dev 持仓过高
- 疑似钓鱼钱包比例异常
- 安全扫描失败且未人工确认继续
- 价格影响超出设定阈值
- 滑点无法接受
- 钱包余额不足或钱包不匹配

## 本地模板

后续 Gateway 本地模板见：

- `infra/hummingbot/docker-compose.gateway.example.yml`
- `infra/hummingbot/README.md`

这些模板不包含私钥，不会自动执行交易。
