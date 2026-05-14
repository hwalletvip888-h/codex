# Hummingbot API Notes

Source: https://github.com/hummingbot/hummingbot-api

## Positioning

Hummingbot API is a backend API for orchestrating multiple Hummingbot trading bots. It is most useful if this project grows from on-chain research into live strategy execution, market making, portfolio monitoring, or multi-exchange bot operations.

It is not a lightweight data SDK. It expects an operational stack around it:

- FastAPI backend on port `8000`
- PostgreSQL on port `5432`
- EMQX MQTT broker on port `1883`
- Optional EMQX dashboard on port `18083`
- Optional Gateway for DEX trading on port `15888`

## What It Adds

- Bot deployment, monitoring, and control
- Portfolio balances, positions, and PnL
- Market data, order books, candles, and funding rates
- Trading endpoints for orders and positions
- Strategy creation and management
- MCP integration through a Dockerized `hummingbot-mcp` service
- Gateway integration for DEX trading

## Fit With This Project

Good fit:

- Running systematic trading bots
- Managing multiple exchange accounts
- Monitoring strategy execution
- Bridging AI assistant workflows into bot control
- Testing market making or arbitrage workflows

Less ideal for the first phase:

- Pure alpha research
- Simple token discovery
- Wallet security scanning
- One-off DEX swaps
- Lightweight opportunity tracking

For those, OKX Onchain OS skills are a cleaner first integration.

## Recommended Integration Path

1. Keep OKX Onchain OS as the first research and on-chain data layer.
2. Treat Hummingbot API as an execution layer candidate.
3. Do not run it against real funds until strategy, credentials, and risk limits are explicit.
4. If adopted, run it in a separate `vendor/hummingbot-api` or sibling workspace instead of mixing its Python/Docker app directly into this lightweight project scaffold.
5. Add a local adapter only after the API is running and authenticated.

## Environment Notes

Important settings from the repository:

- `USERNAME`
- `PASSWORD`
- `CONFIG_PASSWORD`
- `DATABASE_URL`
- `GATEWAY_URL`
- `BROKER_HOST`
- `BROKER_PORT`
- `BROKER_USERNAME`
- `BROKER_PASSWORD`

The README defaults are convenient for local development, but production values must be changed before any real trading use.

## Security Notes

- The API uses HTTP Basic Auth unless debug mode disables it.
- `CONFIG_PASSWORD` encrypts bot credentials.
- Docker access is part of the stack, so the host running this has elevated operational risk.
- Gateway and exchange credentials should be isolated from research-only workflows.

## Decision

Use Hummingbot API later if the project needs real bot orchestration. For the immediate chain-earning research phase, keep it as an evaluated dependency rather than installing or running it now.
