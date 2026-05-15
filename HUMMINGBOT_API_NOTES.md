# Hummingbot API Notes

Sources:

- https://github.com/hummingbot/hummingbot
- https://github.com/hummingbot/gateway
- https://github.com/hummingbot/hummingbot-api
- https://hub.docker.com/r/hummingbot/hummingbot

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

## GitHub Repository Review

### `hummingbot/hummingbot`

This is the main trading bot client. It is useful for running strategy scripts and deployed bots.

Relevant parts:

- `scripts/`: lightweight Python strategy scripts
- `controllers/`: strategy controller framework
- `conf/`: connector, strategy, controller, and script configs
- `docker-compose.yml`: starts `hummingbot/hummingbot:latest`
- Optional Gateway profile starts `hummingbot/gateway:latest` on port `15888`

The Docker compose file mounts local folders into the container:

- `./conf`
- `./conf/connectors`
- `./conf/strategies`
- `./conf/controllers`
- `./conf/scripts`
- `./logs`
- `./data`
- `./scripts`
- `./controllers`

This means it is good for strategy execution after we have stable rules, but it is heavier than needed for the current static meme monitoring dashboard.

### `hummingbot/gateway`

Gateway is the DEX middleware. This is the most relevant Hummingbot repo for Solana execution.

Useful Solana connectors:

- Jupiter: Solana router / aggregator
- Raydium: Solana AMM and CLMM
- Meteora: Solana CLMM

Useful API surface:

- `GET /chains`
- `GET /connectors`
- `GET /chains/solana/status`
- `GET /chains/solana/tokens`
- `GET /chains/solana/balances`
- `GET /chains/solana/poll`
- `GET /connectors/{dex}/router/quote-swap`
- `POST /connectors/{dex}/router/execute-swap`
- `POST /connectors/{dex}/router/execute-quote`

Gateway can run on port `15888`. In development mode it exposes HTTP endpoints. Production mode requires HTTPS certificates.

For this project, Gateway is only useful after we decide to generate executable swap plans. It should not replace OKX Onchain OS for discovery and risk filtering.

### `hummingbot/hummingbot-api`

This is the preferred official stack for multi-bot management.

It starts:

- Hummingbot API on `8000`
- PostgreSQL on `5432`
- EMQX MQTT broker on `1883`
- EMQX Dashboard on `18083`
- Optional Gateway on `15888`

It also supports MCP via `hummingbot/hummingbot-mcp:latest`, which can let AI assistants control bot workflows.

For this project, this is a later-stage orchestration layer rather than a first-stage data source.

## Fit With This Project

Good fit:

- Running systematic trading bots
- Managing multiple exchange accounts
- Monitoring strategy execution
- Bridging AI assistant workflows into bot control
- Testing market making or arbitrage workflows
- Testing Solana execution through Jupiter, Raydium, or Meteora after OKX data filters a token

Less ideal for the first phase:

- Pure alpha research
- Simple token discovery
- Wallet security scanning
- One-off DEX swaps
- Lightweight opportunity tracking
- Graduation monitoring for Solana meme tokens
- Developer, sniper, bundler, and top-holder risk filtering

For those, OKX Onchain OS skills are a cleaner first integration.

## Recommended Integration Path

1. Keep OKX Onchain OS as the first research and on-chain data layer.
2. Treat Hummingbot API as an execution layer candidate.
3. Do not run it against real funds until strategy, credentials, and risk limits are explicit.
4. If adopted, run it in a separate `vendor/hummingbot-api` or sibling workspace instead of mixing its Python/Docker app directly into this lightweight project scaffold.
5. Add a local adapter only after the API is running and authenticated.
6. Start with quote-only / paper execution. Do not broadcast real Solana swaps until OKX risk gates and manual confirmations are in place.

## Proposed Later Architecture

```text
OKX Onchain OS
  -> meme discovery, graduation status, dev risk, sniper/bundler, holder data
  -> docs/data/meme.json
  -> static monitoring dashboard
  -> trade candidate queue
  -> Hummingbot Gateway quote
  -> manual confirmation
  -> Hummingbot / Gateway execution
  -> Hummingbot API portfolio, orders, fills, bot logs
```

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

Use Hummingbot later if the project needs real bot orchestration or Solana DEX execution through Jupiter, Raydium, or Meteora. For the immediate SOL meme monitoring phase, keep OKX Onchain OS as the primary data source and keep Hummingbot as an evaluated execution dependency.

Next detailed plan:

- [Hummingbot Execution Plan](HUMMINGBOT_EXECUTION_PLAN.md)
