import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_ROUTES = new Set(["/", "/login", "/register"]);
const ADMIN_ROUTES = new Set(["/admin", "/monitoring"]);
const PROTECTED_ROUTES = new Set([
  "/dashboard",
  "/query",
  "/reviews",
  "/graph",
  "/corpus",
]);

function decodeJWT(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1];
    const padded = payload.padEnd(payload.length + (4 - (payload.length % 4)) % 4, "=");
    const decoded = Buffer.from(padded, "base64").toString("utf-8");
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_ROUTES.has(pathname);
  const isProtected = PROTECTED_ROUTES.has(pathname) || ADMIN_ROUTES.has(pathname);
  const isAdminRoute = ADMIN_ROUTES.has(pathname);
  const isStatic = pathname.startsWith("/_next") || pathname.startsWith("/favicon") || pathname === "/api/v1";

  if (isStatic || isPublic) {
    return NextResponse.next();
  }

  if (!isProtected) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token")?.value;

  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const payload = decodeJWT(accessToken);
  if (!payload || !payload.sub) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAdminRoute) {
    const role = payload.role;
    if (role !== "admin") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|favicon.ico).*)"],
};
