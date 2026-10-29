const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const cspHeader = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob: https://upload.wikimedia.org https://media.formula1.com;
  font-src 'self' data: https:;
  connect-src 'self' http://localhost:* http://127.0.0.1:*;
  frame-ancestors 'none';
`.replace(/\s{2,}/g, ' ').trim();

/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "upload.wikimedia.org",
      },
      {
        protocol: "https",
        hostname: "media.formula1.com",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: cspHeader },
        ],
      },
      {
        source: "/api/chat/stream",
        headers: [
          { key: "Content-Type", value: "text/event-stream" },
          { key: "Cache-Control", value: "no-cache, no-transform" },
          { key: "Connection", value: "keep-alive" },
          { key: "X-Accel-Buffering", value: "no" },
        ],
      },
      {
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-transform" },
          { key: "X-Accel-Buffering", value: "no" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/live",
        destination: "/live-feed",
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async redirects() {
    return [
      {
        source: "/drivers/:id",
        destination: "/drivers",
        permanent: false,
      },
      {
        source: "/teams/:id",
        destination: "/teams",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;

