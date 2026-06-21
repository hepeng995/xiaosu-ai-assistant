"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BookMarked, Bot, MessageSquare, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { setToken } from "@/lib/auth";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/format";

const HIGHLIGHTS = [
  { icon: BookMarked, title: "RAG 知识库", desc: "带引用 · 可拒答 · 不编造" },
  { icon: Bot, title: "自研 Agent", desc: "LLM 按工具 Schema 自主调度" },
  { icon: MessageSquare, title: "双 IM 接入", desc: "钉钉 / 飞书 一条主链路复用" },
];

/**
 * 管理员登录页：用户名 + 密码 → 后端签发 JWT → 持久化后跳 /admin。
 * 不在 admin 布局下（路径 /login），仅继承根 layout。
 * 左侧 editorial 品牌叙事面板（lg+），右侧表单。
 */
export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.auth.login(username.trim(), password);
      setToken(res.access_token);
      router.replace("/admin");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* ── 左侧：品牌叙事面板（仅 lg+ 显示） ── */}
      <div className="corner-frame relative hidden flex-col justify-between overflow-hidden border-r border-border/60 p-12 lg:flex">
        {/* 翡翠渐变叠加层 + 呼吸光晕 */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/12 via-transparent to-accent/8" />
        <div className="animate-glow-breathe absolute -left-20 top-1/3 h-72 w-72 rounded-full bg-primary/18 blur-3xl" />
        <div className="animate-glow-breathe absolute -right-10 bottom-10 h-56 w-56 rounded-full bg-accent/12 blur-3xl [animation-delay:1.5s]" />

        {/* 顶部品牌徽标 */}
        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
            <Sparkles className="h-5 w-5" strokeWidth={1.6} />
          </div>
          <div className="leading-none">
            <div className="font-display text-2xl font-semibold tracking-tight">小苏</div>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
              AI Atelier · 内部知识助手
            </div>
          </div>
        </div>

        {/* 中段 editorial 大标题 */}
        <div className="relative max-w-md space-y-6">
          <div className="font-mono text-[11px] uppercase tracking-[0.28em] text-primary/80">
            Admin Console
          </div>
          <h1 className="font-display text-[44px] font-semibold leading-[1.1] tracking-tight">
            让每一次
            <br />
            提问都有
            <span className="text-primary"> 据可循</span>
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            基于 RAG 知识库与自研 Tool Calling Agent，在钉钉、飞书与 Web
            后台之间，为员工提供带引用、可拒答、绝不编造的智能问答。
          </p>

          {/* 特性列表 */}
          <ul className="space-y-3 pt-2">
            {HIGHLIGHTS.map((h) => {
              const Icon = h.icon;
              return (
                <li key={h.title} className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-card/70 text-primary ring-1 ring-border">
                    <Icon className="h-4 w-4" strokeWidth={1.6} />
                  </span>
                  <div className="text-sm">
                    <span className="font-medium text-foreground">{h.title}</span>
                    <span className="ml-2 text-muted-foreground">{h.desc}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {/* 底部 mono 版权 */}
        <div className="relative font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/50">
          v0.1.0 — 内部系统 · 请妥善保管凭据
        </div>
      </div>

      {/* ── 右侧：登录表单 ── */}
      <div className="flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-sm animate-fade-in-up">
          {/* 移动端品牌徽标 */}
          <div className="mb-8 flex items-center justify-center gap-3 lg:hidden">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
              <Sparkles className="h-5 w-5" strokeWidth={1.6} />
            </div>
            <div className="leading-none">
              <div className="font-display text-2xl font-semibold tracking-tight">小苏</div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
                AI Atelier
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-primary/80">
              Sign In
            </div>
            <h2 className="font-display text-2xl font-semibold tracking-tight">
              管理后台登录
            </h2>
            <p className="text-sm text-muted-foreground">
              使用管理员账号进入控制台
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                disabled={loading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="请输入密码"
                disabled={loading}
                autoFocus
              />
            </div>
            {error && (
              <p className="rounded-lg border border-destructive/25 bg-destructive/8 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={loading || !username.trim() || !password}
            >
              {loading ? "登录中…" : "进入控制台"}
            </Button>
            <p className="text-center font-mono text-[11px] text-muted-foreground/70">
              开发环境默认 admin / admin123（生产请走环境变量）
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
