import type { NextConfig } from "next";

const apiOrigin = process.env.API_INTERNAL_URL ?? "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
