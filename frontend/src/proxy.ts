import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { isLoopbackHostHeader, isLoopbackOrigin } from "@/lib/security/loopback";

export function proxy(request: NextRequest) {
  if (!isLoopbackHostHeader(request.headers.get("host"))) {
    return NextResponse.json(
      { detail: "Hey Canvas is only available on this computer." },
      { status: 403 },
    );
  }
  const origin = request.headers.get("origin");
  if (origin !== null && !isLoopbackOrigin(origin)) {
    return NextResponse.json(
      { detail: "This request was blocked for your privacy." },
      { status: 403 },
    );
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*", "/health"],
};
