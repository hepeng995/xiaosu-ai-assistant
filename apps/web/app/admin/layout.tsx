"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bug,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { ThemeToggle } from "@/components/admin/theme-toggle";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/admin", label: "概览", icon: LayoutDashboard, no: "01" },
  { href: "/admin/documents", label: "文档管理", icon: FileText, no: "02" },
  { href: "/admin/logs", label: "对话日志", icon: MessageSquare, no: "03" },
  { href: "/admin/settings", label: "系统设置", icon: Settings, no: "04" },
  { href: "/admin/chat", label: "调试聊天", icon: Bug, no: "05" },
];

function isActive(pathname: string, href: string): boolean {
  // "/admin" 概览页须精确匹配，否则会对所有子路由都高亮。
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, logout } = useAuth();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  // 未登录（含 SSR 首屏 token=null）不渲染后台内容，等待跳登录
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="relative flex min-h-dvh">
      {/* 侧边栏：移动端为抽屉，桌面端（md+）固定 */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[calc(100vw-1rem)] max-w-[18rem] transform flex-col border-r border-border/70 bg-card/80 backdrop-blur-xl transition-transform duration-300 ease-out md:w-72",
          "md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* 品牌区 —— editorial 衬线品牌名 */}
        <div className="corner-frame relative border-b border-border/60 px-6 py-6">
          <div className="flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-3">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12 text-primary ring-1 ring-primary/25">
                <Sparkles className="h-5 w-5" strokeWidth={1.6} />
              </div>
              <div className="leading-none">
                <div className="font-display text-xl font-semibold tracking-tight">
                  小苏
                </div>
                <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                  AI Atelier
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
              aria-label="关闭菜单"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* 导航 —— 编号 + 活跃竖条指示 */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-5">
          <div className="mb-2 px-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60">
            Navigate
          </div>
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                {/* 活跃项左侧竖条指示 */}
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
                )}
                <span
                  className={cn(
                    "font-mono text-[10px] tabular-nums transition-colors",
                    active
                      ? "text-primary/70"
                      : "text-muted-foreground/40 group-hover:text-muted-foreground/70",
                  )}
                >
                  {item.no}
                </span>
                <Icon
                  className="h-4 w-4 shrink-0"
                  strokeWidth={active ? 2 : 1.6}
                />
                <span className={cn(active && "font-display tracking-tight")}>
                  {item.label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* 退出登录 */}
        <div className="border-t border-border/60 p-3">
          <button
            type="button"
            onClick={handleLogout}
            className="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <span className="font-mono text-[10px] text-muted-foreground/40 group-hover:text-destructive/60">
              ⏻
            </span>
            <LogOut className="h-4 w-4 shrink-0" strokeWidth={1.6} />
            退出登录
          </button>
        </div>

        {/* 运行状态 + 主题切换 —— 精密状态灯 */}
        <div className="border-t border-border/60 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success shadow-[0_0_8px_var(--success)]" />
              </span>
              服务运行中
            </div>
            <ThemeToggle />
          </div>
          <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/50">
            v0.1.0 · 内部系统
          </div>
        </div>
      </aside>

      {/* 抽屉遮罩（仅移动端） */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* 主区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 移动端顶部栏 */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border/60 bg-card/80 px-3 py-3 backdrop-blur-xl md:hidden">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="-ml-1 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="打开菜单"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2 font-display font-semibold tracking-tight">
            <Sparkles className="h-4 w-4 text-primary" />
            小苏
          </div>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1 overflow-auto p-3 sm:p-4 md:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
