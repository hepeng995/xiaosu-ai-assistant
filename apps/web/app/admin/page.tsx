"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  Bug,
  CircleDollarSign,
  Database,
  FileText,
  Files,
  MessageSquare,
  Zap,
} from "lucide-react";
import { api, type DocumentItem, type MessageItem } from "@/lib/api";
import { PageHeader } from "@/components/admin/page-header";
import { StatCard } from "@/components/admin/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, shortTime } from "@/lib/format";
import { summarize } from "@/lib/stats";

const QUICK_LINKS = [
  {
    href: "/admin/documents",
    label: "管理文档",
    desc: "上传与维护知识库",
    icon: FileText,
  },
  {
    href: "/admin/logs",
    label: "对话日志",
    desc: "工具调用与 Token 消耗",
    icon: MessageSquare,
  },
  {
    href: "/admin/chat",
    label: "调试聊天",
    desc: "测试 RAG 检索效果",
    icon: Bug,
  },
];

export default function DashboardPage() {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [msgRes, docRes] = await Promise.all([
        api.messages.list(200),
        api.documents.list(),
      ]);
      setMessages(msgRes.items);
      setDocs(docRes.items);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const run = async () => {
      await load();
    };
    run();
  }, [load]);

  const stats = summarize(messages, docs);
  const recent = messages.slice(0, 8);
  const successTone =
    stats.successRate >= 90
      ? "success"
      : stats.successRate >= 60
        ? "warning"
        : "destructive";

  return (
    <div className="space-y-5 sm:space-y-6">
      <PageHeader
        eyebrow="Overview · 01"
        title="概览"
        description="知识库与对话的整体运行情况"
      />

      {error && (
        <p className="rounded-lg border border-destructive/25 bg-destructive/8 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* 统计卡网格 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 lg:gap-4">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 sm:h-[104px]" />
          ))
        ) : (
          <>
            <StatCard label="文档总数" value={stats.docTotal} icon={Files} />
            <StatCard
              label="已索引"
              value={stats.docIndexed}
              icon={Database}
              tone="success"
            />
            <StatCard
              label="对话消息"
              value={stats.msgTotal}
              icon={MessageSquare}
            />
            <StatCard
              label="回复成功率"
              value={`${stats.successRate}%`}
              icon={Activity}
              tone={successTone}
              hint={`${stats.assistantTotal} 条助手回复`}
            />
            <StatCard
              label="累计 Token"
              value={stats.totalTokens.toLocaleString()}
              icon={Zap}
            />
            <StatCard
              label="累计成本"
              value={`$${stats.totalCost.toFixed(4)}`}
              icon={CircleDollarSign}
            />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        {/* 最近对话 */}
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0 p-4 sm:p-6">
            <CardTitle className="text-base">最近对话</CardTitle>
            <Link
              href="/admin/logs"
              className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-primary"
            >
              查看全部 →
            </Link>
          </CardHeader>
          <CardContent className="space-y-1 p-4 pt-0 sm:p-6 sm:pt-0">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))
            ) : recent.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                暂无对话记录
              </p>
            ) : (
              recent.map((m) => (
                <div
                  key={m.id}
                  className="group flex flex-col gap-2 rounded-lg border border-transparent px-2 py-2 text-sm transition-colors hover:border-border/60 hover:bg-primary/[0.03] sm:flex-row sm:items-center sm:gap-3"
                >
                  <div className="flex flex-wrap items-center gap-2 sm:contents">
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground sm:w-16">
                      {shortTime(m.created_at)}
                    </span>
                    <Badge variant="outline" className="shrink-0 normal-case">
                      {m.platform}
                    </Badge>
                    {!m.success && (
                      <Badge variant="destructive" className="shrink-0 sm:hidden">
                        失败
                      </Badge>
                    )}
                  </div>
                  <span className="min-w-0 break-words text-muted-foreground group-hover:text-foreground sm:flex-1 sm:truncate">
                    {m.content}
                  </span>
                  {!m.success && (
                    <Badge variant="destructive" className="hidden shrink-0 sm:inline-flex">
                      失败
                    </Badge>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* 快捷入口 */}
        <div className="grid gap-3">
          {QUICK_LINKS.map((q) => {
            const Icon = q.icon;
            return (
              <Link key={q.href} href={q.href} className="glow-ring group block">
                <Card className="flex items-center gap-3 p-3 sm:gap-4 sm:p-4">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                    <Icon className="h-5 w-5" strokeWidth={1.7} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-base font-medium tracking-tight">
                      {q.label}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {q.desc}
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground transition-all duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
