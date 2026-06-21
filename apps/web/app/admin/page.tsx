"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  CircleDollarSign,
  Database,
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
    <div className="space-y-4">
      <PageHeader title="概览" description="知识库与对话的整体运行情况" />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px]" />
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">最近对话</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10" />
            ))
          ) : recent.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              暂无对话记录
            </p>
          ) : (
            recent.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 border-b border-border/60 pb-2 text-sm last:border-0 last:pb-0"
              >
                <span className="w-24 shrink-0 text-xs text-muted-foreground">
                  {shortTime(m.created_at)}
                </span>
                <Badge variant="outline" className="shrink-0">
                  {m.platform}
                </Badge>
                <span className="min-w-0 flex-1 truncate">{m.content}</span>
                {!m.success && (
                  <Badge variant="destructive" className="shrink-0">
                    失败
                  </Badge>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-4 text-sm">
        <Link href="/admin/documents" className="text-primary hover:underline">
          → 管理文档
        </Link>
        <Link href="/admin/logs" className="text-primary hover:underline">
          → 查看对话日志
        </Link>
        <Link href="/admin/chat" className="text-primary hover:underline">
          → 调试聊天
        </Link>
      </div>
    </div>
  );
}
