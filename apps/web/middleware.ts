import { NextResponse, type NextRequest } from "next/server";

/**
 * SSR 层路由保护：未登录访问 /admin/* 直接重定向到 /login，避免 client 端
 * useEffect 兜底导致的首屏白屏闪。token 由 lib/auth.ts 在登录时同步写入 cookie。
 *
 * 保留 admin/layout.tsx 的 client 端检查作二次兜底（应对 token 过期等场景）。
 */
const TOKEN_COOKIE = "xiaosu-token";

export function middleware(request: NextRequest) {
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("from", request.nextUrl.pathname + request.nextUrl.search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
