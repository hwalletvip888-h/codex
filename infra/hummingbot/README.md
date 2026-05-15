# Hummingbot Local Templates

本目录只放后续执行层模板，不参与当前静态面板的数据抓取。

## 当前用途

- 记录 Hummingbot Gateway 的本地启动方式
- 后续做 quote-only 测试
- 不保存私钥
- 不自动下单

## 启动 Gateway 示例

复制模板：

```powershell
Copy-Item infra/hummingbot/docker-compose.gateway.example.yml infra/hummingbot/docker-compose.yml
```

启动：

```powershell
docker compose -f infra/hummingbot/docker-compose.yml up -d
```

默认端口：

- Gateway: `http://localhost:15888`
- Swagger: `http://localhost:15888/docs`

## 安全边界

- `GATEWAY_PASSPHRASE` 只用于本地开发示例，正式环境必须替换。
- 不要把钱包私钥、助记词、真实 API Secret 写进本目录。
- 当前项目第一阶段只用 OKX Onchain OS 拉数据。
- Gateway 后续先用于报价，不用于自动执行。
