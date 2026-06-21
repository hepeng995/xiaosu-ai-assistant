"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bug,
  FileText,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { ThemeToggle } from "@/components/admin/theme-toggle";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/admin", label: "概览", icon: LayoutDashboard },
  { href: "/admin/documents", label: "文档管理", icon: FileText },
  { href: "/admin/logs", label: "对话日志", icon: MessageSquare },
  { href: "/admin/settings", label: "系统设置", icon: Settings },
  { href: "/admin/chat", label: "调试聊天", icon: Bug },
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
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/40">
      {/* 侧边栏：移动端为抽屉，桌面端（md+）固定 */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 transform flex-col border-r border-border bg-card transition-transform duration-200 ease-out",
          "md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* 品牌区 */}
        <div className="flex items-center justify-between gap-2.5 border-b border-border px-5 py-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">小苏</div>
              <div className="text-xs text-muted-foreground">AI 助手后台</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
            aria-label="关闭菜单"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 导航 */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* 运行状态 + 主题切换 */}
        <div className="border-t border-border px-5 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              服务运行中
            </div>
            <ThemeToggle />
          </div>
          <div className="mt-1.5 text-[11px] text-muted-foreground/60">
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
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-card/95 px-4 py-3 backdrop-blur md:hidden">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="-ml-1 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="打开菜单"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2 font-semibold">
            <Sparkles className="h-4 w-4 text-primary" />
            小苏后台
          </div>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
