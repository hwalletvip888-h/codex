# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## 项目概述

H AI 量化平台 — 基于 onchainos CLI 链上数据的 AI 量化交易系统。当前处于初始化阶段。

## 技术栈

- Python 3.11+ (数据分析 + 策略引擎)
- onchainos CLI (链上数据源)
- OKX DEX API (交易执行)

## 项目结构

```
H AI量化平台/
├── data/           # 数据缓存与存储
├── strategies/     # 交易策略模块
├── backtest/       # 回测引擎
├── execution/      # 交易执行层
├── analysis/       # 信号分析与报告
├── config/         # 配置文件
└── scripts/        # 运行脚本
```

## 开发原则

- 实用主义优先，不过度工程化
- 每个策略独立可测试
- 数据驱动决策，所有信号基于链上数据
- 中文注释，英文代码标识符

## 环境

- Windows 11 Pro
- PowerShell 5.1 + Bash (Git)
- Python 虚拟环境管理依赖
