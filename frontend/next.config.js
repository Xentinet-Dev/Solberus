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
      {
        source: '/ws/:path*',
        destination: 'ws://localhost:8000/ws/:path*', // WebSocket proxy
      },
    ];
  },
};

module.exports = nextConfig;

