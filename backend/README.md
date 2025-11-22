# Solberus Backend

FastAPI backend for Solana trading bot operations.

## Installation

`ash
uv sync --extra web
`

## Configuration

1. Copy .env.example to .env
2. Configure your Solana RPC endpoints
3. Add your wallet private key
4. Configure bot YAML files in ots/ directory

## Running

`ash
uvicorn src.web.api_server:app --host 0.0.0.0 --port 8000
`

## API Documentation

Once running, visit:
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Bot Configuration

Edit YAML files in ots/ directory to configure trading strategies.
