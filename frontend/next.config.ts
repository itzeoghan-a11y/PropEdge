import type { NextConfig } from "next";

// API_URL is server-only (read at build/request time on Vercel), so we can
// rotate the backend URL without rebuilding the client bundle. Falls back to
// NEXT_PUBLIC_API_URL for local dev if someone already set that.
const backend =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
