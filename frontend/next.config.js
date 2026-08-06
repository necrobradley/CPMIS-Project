/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  async rewrites() {
    return [
      {
        source: '/api-proxy/:path*',
        destination: `${process.env.API_PROXY_TARGET || 'http://localhost:8000'}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
