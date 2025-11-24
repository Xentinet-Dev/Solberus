/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: [],
  },
  // If your API is on a different origin, configure CORS
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // Your FastAPI server
      },
      // WebSocket connections handled directly by NEXT_PUBLIC_WS_URL in .env.local
    ];
  },
};

module.exports = nextConfig;

