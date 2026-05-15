# Onchain OS

链上 meme 币策略项目初始化骨架，当前目标是先建立一个清晰、可扩展、便于后续接入 OKX Onchain OS / Web3 工具链的工作区。

> 说明：本项目用于链上数据、策略、自动化流程与风险控制的研发，不构成投资建议，也不承诺收益。

## 项目方向

- Meme 新币发现：跟踪新池子、热门 token、聪明钱钱包、交易量和社群热度。
- 策略工作流：把发现、过滤、买入计划、止损止盈、复盘拆成可追踪流程。
- 风险控制：记录资金暴露、授权、合约风险、Gas 成本与退出条件。
- OKX Onchain OS 集成：优先使用 DEX、token、market、signal、trenches 和 security 相关能力。

## 官方资料

- OKX Onchain OS Skills: https://github.com/okx/onchainos-skills
- OKX Onchain OS Dev Docs: https://web3.okx.com/zh-hans/onchainos/dev-docs/home/what-is-onchainos
- Hummingbot API: https://github.com/hummingbot/hummingbot-api

## 快速开始

```powershell
npm run check
```

静态策略面板：

- GitHub Pages: https://hwalletvip888-h.github.io/codex/
- 本地文件: [docs/index.html](docs/index.html)

更新真实数据：

```powershell
npm run fetch:meme
```

该命令会调用 OKX Onchain OS，生成 `docs/data/meme.json`，面板会读取这个文件展示未毕业和刚毕业的 Solana meme 币数据。

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后按需填写 API Key、钱包地址和链配置。不要把 `.env` 提交到 Git。

## 目录

```text
.
├─ docs/
│  ├─ PROJECT_BRIEF.md
│  ├─ PROJECT_MEMORY.md
│  ├─ MEME_STRATEGY.md
│  └─ RISK_CONTROL.md
├─ scripts/
│  └─ check-env.js
├─ .env.example
├─ .gitignore
├─ package.json
└─ README.md
```

## 下一步建议

1. 确认项目优先形态：数据看板、自动化 Agent、命令行工具，或交易/任务执行器。
2. 接入 OKX Onchain OS 的 token、market、signal、security 和 trenches 能力。
3. 建立第一版 meme token 观察池、风险评分表和交易复盘表。
4. 先做半自动提醒与人工确认，再决定是否接钱包签名和交易广播。

## 参考评估

- [Hummingbot API Notes](docs/HUMMINGBOT_API_NOTES.md)
- [Hummingbot Execution Plan](docs/HUMMINGBOT_EXECUTION_PLAN.md)
- [Meme Strategy](docs/MEME_STRATEGY.md)
- [Project Memory](docs/PROJECT_MEMORY.md)
- [Data Integration Matrix](docs/DATA_INTEGRATION_MATRIX.md)
