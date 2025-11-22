# Solberus

Adaptive Solana trading intelligence for on-chain risk analysis, MEV-aware execution, and structured liquidity management.

> **Status:** Early-stage, actively evolving.  
> **Disclaimer:** This software is experimental and not financial advice.

---

## Overview

**Solberus** is an on-chain trading and risk-intelligence engine built for high-velocity Solana markets.

It is designed to:

1. **Interrogate tokens and contracts before capital is committed** – authorities, LP structure, holder distribution, deployer history, and basic behavioral red flags.

2. **Translate that intelligence into disciplined execution** – position sizing, structured entries, risk limits, and automated exits.

The core objective is to give individual traders and small teams tooling that behaves more like an institutional execution and risk stack, but tuned for early-stage, volatile DeFi assets.

---

## Key Capabilities

### On-Chain Contract & Market Intelligence

- **Contract-level checks:**
  - Mint and freeze authority state
  - Upgradeability / ownership patterns (where applicable)
  - Basic honeypot / "cannot exit" configurations
  - Comprehensive threat detection and contract auditing

- **Liquidity pool analysis:**
  - LP lock / unlock state
  - LP concentration and asymmetry
  - Sudden LP additions/removals
  - Liquidity health monitoring

- **Holder distribution:**
  - Top-holder concentration
  - Early-holder clustering
  - Deployer or affiliated wallet allocation share
  - Whale tracking and mimicry strategies

- **Deployer and address heuristics:**
  - Reused deployers across multiple tokens
  - Patterns of prior failures or hostile behavior
  - Social signal intelligence from multiple platforms

### Risk Scoring & Decision Layer

- Aggregated **risk score** per asset based on:
  - Contract configuration
  - Liquidity topology
  - Holder and deployer structure
  - Social sentiment and signals

- Configurable rulesets:
  - "Reject if top N holders > X% total supply"
  - "Reduce size if LP unlocks inside threshold window"
  - "Skip assets from known hostile deployers"

- Adaptive risk management with position sizing

### Execution & Liquidity Management

- **Multi-platform support:**
  - pump.fun integration
  - LetsBonk integration
  - Universal trading interface

- **Order construction and routing:**
  - Market and limit-style entries
  - Slippage-aware order sizing for illiquid pairs
  - Priority fee management (dynamic and fixed)

- **Position and lifecycle management:**
  - Structured entries (single-shot or scaled)
  - Laddered or staged exits
  - Price- or time-based risk limits

- **Portfolio-level guards:**
  - Per-asset exposure caps
  - Global exposure caps
  - Environment-level kill switches

### Advanced Strategies

- **MEV Protection & Execution:**
  - Jito integration for bundle transactions
  - Front-running detection and protection
  - Sandwich attack mitigation
  - Mempool monitoring

- **Arbitrage Engine:**
  - Cross-platform price monitoring
  - Automated arbitrage opportunity detection
  - Execution routing

- **Market Making:**
  - Inventory management
  - Spread calculation
  - Automated liquidity provision

- **AI-Powered Intelligence:**
  - Token evaluation using ML models
  - Event prediction
  - Sentiment analysis from social platforms
  - Smart money tracking

---

## Architecture

Solberus is structured as a three-layer system:

1. ### Analysis Layer (Perception)
   - Discovers and ingests candidate assets via multiple listeners (Geyser, Logs, Blocks, PumpPortal)
   - Pulls contract, LP, and holder data from RPC/indexers
   - Normalizes raw information into a structured feature set
   - Social signal intelligence from Twitter, Telegram, Discord, Reddit

2. ### Decision Layer (Risk & Strategy Engine)
   - Computes asset-level risk scores using configurable heuristics
   - Applies strategy profiles (conservative, standard, aggressive)
   - Security scanning and threat detection
   - Outputs a decision object with status (reject/watch/eligible), recommended position size, entry/exit patterns

3. ### Execution Layer (Trade Engine)
   - Interfaces with Solana, DEX routers, and wallets
   - Builds and sends transactions via Jito bundles or direct execution
   - Tracks live positions and applies lifecycle rules (TP/SL/timeout)
   - Web API for monitoring and control

---

## Repository Structure

```text
Solberus/
├── backend/                    # Python/FastAPI backend
│   ├── src/
│   │   ├── security/          # Contract auditing, threat detection
│   │   ├── risk/              # Risk scoring, position sizing
│   │   ├── trading/           # Universal trading interface
│   │   ├── platforms/         # pump.fun, LetsBonk integrations
│   │   ├── monitoring/        # Event listeners (Geyser, Logs, Blocks)
│   │   ├── mev/               # MEV strategies and protection
│   │   ├── arbitrage/         # Arbitrage engine
│   │   ├── market_making/     # Market making strategies
│   │   ├── liquidity/         # Liquidity management
│   │   ├── intelligence/      # Social signals, whale tracking
│   │   ├── ai/                # ML models, token evaluation
│   │   ├── execution/         # Transaction building, Jito integration
│   │   ├── web/               # FastAPI server and WebSocket
│   │   └── core/              # RPC client, wallet, priority fees
│   ├── bots/                  # Bot configuration YAML files
│   ├── idl/                   # Solana program IDL files
│   ├── pyproject.toml         # Python dependencies
│   └── .env.example           # Environment configuration template
│
└── frontend/                   # Next.js/React dashboard
    ├── app/                   # Next.js app directory
    ├── components/            # React components (dashboard, tabs, forms)
    ├── lib/                   # API clients and utilities
    ├── store/                 # Zustand state management
    └── package.json           # Node.js dependencies
```

---

## Prerequisites

- **Python** 3.9+ (3.11+ preferred)
- **uv** package manager ([install guide](https://github.com/astral-sh/uv))
- **Node.js** 18+ (20+ preferred)
- **npm** or **yarn**
- A **Solana RPC endpoint** (Helius, Triton, QuickNode, or self-hosted)
- A **Solana keypair** dedicated for this system (not your main wallet)
- (Optional) **Geyser endpoint** for fastest token detection
- (Optional) Access to social platform APIs for intelligence features

---

## Installation

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/Xentinet-Dev/Solberus.git
cd Solberus/backend

# Install dependencies
uv sync --extra web

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Frontend Setup

```bash
# From repository root
cd frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local
# Edit .env.local with your API URL
```

---

## Configuration

Sensitive configuration is provided via environment variables.

### Backend Configuration (`.env`)

```bash
# Solana RPC Configuration
SOLANA_NODE_RPC_ENDPOINT=https://your-rpc-endpoint.com
SOLANA_NODE_WSS_ENDPOINT=wss://your-wss-endpoint.com

# Solana Wallet Private Key
# IMPORTANT: Keep this secret! Never commit this file.
SOLANA_PRIVATE_KEY=your_private_key_here

# Geyser Configuration (Optional - for fastest token detection)
GEYSER_ENDPOINT=your_geyser_endpoint_here
GEYSER_API_TOKEN=your_geyser_api_token_here

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your_api_key_here

# Security
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

### Frontend Configuration (`.env.local`)

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket Configuration
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### Bot Configuration

Edit YAML files in `backend/bots/` directory to configure trading strategies. Each file represents a separate bot instance.

Example configuration:

```yaml
name: "bot-sniper-1"
platform: "pump_fun"
enabled: true
listener_type: "geyser"  # or "logs", "blocks", "pumpportal"
trade:
  buy_amount: 0.0001
  buy_slippage: 0.3
  sell_slippage: 0.3
  exit_strategy: "time_based"
```

> **Security:** Do not commit `.env` or any private keys. Ensure `.gitignore` covers them.

---

## Running Solberus

### 1. Start Backend API Server

```bash
cd backend
uvicorn src.web.api_server:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 2. Start Frontend Dashboard

```bash
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser.

### 3. Run Trading Bots

Bots can be configured via YAML files in `backend/bots/` and controlled through:
- Web dashboard (recommended)
- API endpoints
- Direct bot runner: `uv run src.bot_runner`

---

## Operating Modes

### Web Dashboard Mode (Recommended)

- Full monitoring and control via web interface
- Real-time position tracking
- Strategy configuration
- Risk monitoring
- Performance analytics

### API-Only Mode

- Headless operation
- Programmatic control via REST API
- WebSocket for real-time updates
- Suitable for automation and integration

---

## Security Considerations

Because Solberus can control a wallet and initiate trades, it must be treated as production-grade infrastructure:

### Key Management

- Prefer keypair files or secure key storage over raw private keys in environment variables
- Never log seeds or private keys
- Limit access to any machine running Solberus

### Wallet Segregation

- Run Solberus from a dedicated hot wallet
- Keep the majority of capital in cold storage or unrelated wallets

### Infrastructure Hardening

- Restrict incoming network ports
- Use SSH keys and minimal privileges on servers
- Protect logs and configuration files with proper OS-level permissions
- Enable rate limiting on API endpoints

### Monitoring & Auditability

- Persist logs of decisions and executed trades
- Regularly review outcomes and adjust thresholds and strategies
- Use the web dashboard for real-time monitoring

---

## Development

### Backend Development

```bash
cd backend
uv sync --extra web --extra dev
uv run pytest  # Run tests
```

### Frontend Development

```bash
cd frontend
npm run dev
npm run lint
```

---

## Production Deployment

### Backend

The backend can be deployed using:
- Docker (create Dockerfile)
- Systemd service
- Process managers (PM2, supervisor)
- Cloud platforms (Render, Railway, AWS, DigitalOcean)

### Frontend

Build for production:

```bash
cd frontend
npm run build
npm start
```

Deploy to:
- Vercel (recommended for Next.js)
- Netlify
- AWS Amplify
- Any static hosting service

---

## Disclaimers

* This codebase is **experimental** and not audited.
* There is no guarantee of correctness, profitability, or safety.
* Market conditions, adversarial behavior, and infrastructure failures can all lead to losses.
* You are solely responsible for how you deploy and operate this system.
* Nothing in this repository constitutes financial advice or a recommendation to trade.

---

## Roadmap

* [ ] Enhanced MEV-surface analysis for Solana
* [ ] Deeper deployer and address-cluster analytics
* [ ] Web dashboard enhancements for visualizing scores, positions, and performance
* [ ] Pluggable strategy modules with versioned configs
* [ ] Multi-chain abstraction and support
* [ ] Formal test harness for strategy backtesting on historical data
* [ ] Advanced AI model training and deployment

---

## Contributing

Contributions focused on robustness, clarity, and safety are welcome:

* Improved heuristics for contract and LP risk
* Additional data-source integrations (indexers, DEXs, MEV relays)
* Test coverage and simulation frameworks
* Documentation and operational runbooks

Typical flow:

```bash
git checkout -b feature/<short-description>
# implement changes
uv run pytest        # or your test runner
git commit -am "Describe the change"
git push origin feature/<short-description>
# open a Pull Request
```

---

## License

See [LICENSE](LICENSE) file for details.

---

## Contact / Metadata

* **Project:** Solberus – Adaptive Solana Trading Intelligence
* **Focus:** On-chain risk analysis, MEV-aware execution, and structured liquidity management
* **Repository:** https://github.com/Xentinet-Dev/Solberus
* **Issues / Bugs:** Please open a GitHub Issue with environment details, logs, and reproduction steps.
