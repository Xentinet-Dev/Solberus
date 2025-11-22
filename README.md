# Solberus

Professional-grade Solana trading bot for pump.fun and LetsBonk platforms.

## Overview

Solberus is a production-ready trading bot system with a modern web interface for monitoring and controlling Solana token trading operations. The system consists of a FastAPI backend and a Next.js frontend.

## Features

- Multi-platform trading (pump.fun, LetsBonk)
- Security scanning and threat detection
- Real-time monitoring dashboard
- MEV, Market Making, and Arbitrage strategies
- Wallet-based authentication
- Performance analytics
- WebSocket real-time updates

## Architecture

`
Solberus/
â”œâ”€â”€ backend/          # FastAPI trading bot backend
â”‚   â”œâ”€â”€ src/         # Core trading logic
â”‚   â”œâ”€â”€ bots/        # Bot configuration files
â”‚   â””â”€â”€ idl/         # Solana program IDL files
â””â”€â”€ frontend/        # Next.js web dashboard
    â”œâ”€â”€ app/         # Next.js app directory
    â”œâ”€â”€ components/  # React components
    â””â”€â”€ lib/         # Utilities and API clients
`

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher
- uv package manager (for Python)
- npm or yarn (for Node.js)

### Backend Setup

1. Navigate to backend directory:
   `ash
   cd backend
   `

2. Install dependencies:
   `ash
   uv sync --extra web
   `

3. Copy environment template:
   `ash
   copy .env.example .env
   `

4. Edit .env file with your Solana RPC endpoints and private key.

5. Start the API server:
   `ash
   uvicorn src.web.api_server:app --host 0.0.0.0 --port 8000
   `

### Frontend Setup

1. Navigate to frontend directory:
   `ash
   cd frontend
   `

2. Install dependencies:
   `ash
   npm install
   `

3. Copy environment template:
   `ash
   copy .env.example .env.local
   `

4. Edit .env.local with your API URL (default: http://localhost:8000).

5. Start development server:
   `ash
   npm run dev
   `

6. Open http://localhost:3000 in your browser.

## Configuration

### Bot Configuration

Edit YAML files in ackend/bots/ directory to configure trading strategies. Each file represents a separate bot instance.

Example configuration:
`yaml
name: "bot-sniper-1"
platform: "pump_fun"
enabled: true
trade:
  buy_amount: 0.0001
  buy_slippage: 0.3
  sell_slippage: 0.3
`

### Environment Variables

See .env.example files in both backend and frontend directories for required configuration.

## Development

### Backend Development

`ash
cd backend
uv sync --extra web --extra dev
uv run pytest
`

### Frontend Development

`ash
cd frontend
npm run dev
npm run lint
`

## Production Deployment

### Backend

The backend can be deployed using:
- Docker (create Dockerfile)
- Systemd service
- Process managers (PM2, supervisor)
- Cloud platforms (Render, Railway, AWS)

### Frontend

Build for production:
`ash
cd frontend
npm run build
npm start
`

Deploy to:
- Vercel (recommended for Next.js)
- Netlify
- AWS Amplify
- Any static hosting service

## Security

- Never commit .env files
- Use strong API keys
- Enable rate limiting in production
- Use HTTPS in production
- Validate all wallet signatures
- Keep dependencies updated

## License

[Your License Here]

## Support

For issues and questions, please open an issue on the repository.
