# Solberus Frontend

Next.js dashboard for monitoring and controlling the Solberus trading bot.

## Installation

`ash
npm install
`

## Configuration

1. Copy .env.example to .env.local
2. Set NEXT_PUBLIC_API_URL to your backend API URL

## Development

`ash
npm run dev
`

Open http://localhost:3000

## Production Build

`ash
npm run build
npm start
`

## Project Structure

- pp/ - Next.js app directory with pages
- components/ - React components
- lib/ - Utilities and API clients
- store/ - Zustand state management
