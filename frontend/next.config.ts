import type { NextConfig } from "next";

import { resolveBackendOrigin } from "./src/lib/api/http/backend-origin";

const backendOrigin = resolveBackendOrigin();
const isolatedDistDir = process.env.HEY_CANVAS_NEXT_DIST_DIR?.trim();

const nextConfig: NextConfig = {
  ...(isolatedDistDir ? { distDir: isolatedDistDir } : {}),
  async rewrites() {
    return [
      { source: "/health", destination: `${backendOrigin}/health` },
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
    ];
  },
};

export default nextConfig;
