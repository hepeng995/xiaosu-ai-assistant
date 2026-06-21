"use client";

import { useCallback, useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import { api, type MessageItem } from "@/lib/api";
import { EmptyState } from "@/components/admin/empty-state";
import { PageHeader } from "@/components/admin/page-header";
import { Segmented } from "@/components/admin/segmented";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cost, errorMessage, latency, shortTime } from "@/lib/format";
import { ErrorBanner } from "@/components/admin/error-banner";
import { MessageDetail } from "@/components/admin/message-detail";

const STATUS_FILTERS = [
  { value: "all", label: "全部" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

const PLATFORM_FILTERS = [
  { value: "all", label: "全部" },
  { value: "web", label: "Web" },
  { value: "dingtalk", label: "钉钉" },
  { value: "feishu", label: "飞书" },
];

function toolNames(message: MessageItem): string {
  return (
    (message.tool_calls as { name: string }[] | null)
      ?.map((tool) => tool.name)
      .join(",") ?? ""
  );
}

export default function LogsPage() {
  const [items, setItems] = useState<MessageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const load = useCallback(async () => {
    try {
      const data = await api.messages.list(100);
      setItems(data.items);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  useEffect(() => {
    const run = async () => {
      await load();
    };
    run();
  }, [load]);

  const filtered = items.filter((m) => {
    const keyword = search.toLowerCase();
    const matchSearch =
      !keyword ||
      m.content.toLowerCase().includes(keyword) ||
      (m.user_name ?? m.user_id ?? "").toLowerCase().includes(keyword);
    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "success" ? m.success : !m.success);
    const matchPlatform =
      platformFilter === "all" || m.platform === platformFilter;
    return matchSearch && matchStatus && matchPlatform;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paged = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Logs · 03"
        title="对话日志"
        description="查看历史对话、工具调用与 Token 消耗"
      >
        <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
          {refreshing ? "刷新中…" : "刷新"}
        </Button>
      </PageHeader>

      <div className="grid gap-3 sm:flex sm:flex-wrap sm:items-center">
        <Input
          placeholder="搜索内容或用户…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-xs"
        />
        <Segmented
          options={STATUS_FILTERS}
          value={statusFilter}
          onChange={setStatusFilter}
        />
        <Segmented
          options={PLATFORM_FILTERS}
          value={platformFilter}
          onChange={setPlatformFilter}
        />
      </div>

      {error && <ErrorBanner message={error} />}

      {!loading && filtered.length > 0 && (
        <p className="font-mono text-xs text-muted-foreground">
          共 {filtered.length} 条消息 ·{" "}
          {new Set(filtered.map((m) => m.conversation_id)).size} 个会话
          <span className="ml-2">（点击行展开工具调用详情）</span>
        </p>
      )}

      <div className="space-y-3 md:hidden">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))
        ) : filtered.length === 0 ? (
          <Card>
            <CardContent className="p-4">
              <EmptyState
                icon={Inbox}
                title={items.length === 0 ? "暂无对话记录" : "没有匹配的记录"}
                description={
                  items.length === 0
                    ? "员工在 IM 中 @ 机器人后，对话会记录在这里"
                    : "试试调整搜索或筛选条件"
                }
              />
            </CardContent>
          </Card>
        ) : (
          paged.map((m) => {
            const tools = toolNames(m);
            return (
              <Card key={m.id} className="corner-frame">
                <CardContent className="space-y-3 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                      {shortTime(m.created_at)}
                    </span>
                    <Badge variant={m.success ? "secondary" : "destructive"}>
                      {m.success ? "成功" : "失败"}
                    </Badge>
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium">{m.platform} · {m.role}</div>
                    <div className="break-words text-xs text-muted-foreground">
                      {m.user_name || m.user_id}
                    </div>
                  </div>
                  <p className="whitespace-pre-wrap break-words rounded-lg bg-muted/45 p-3 text-sm leading-6">
                    {m.content}
                  </p>
                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg bg-background/55 p-2">
                      <dt className="text-muted-foreground">工具</dt>
                      <dd className="mt-1 break-words text-primary">{tools || "—"}</dd>
                    </div>
                    <div className="rounded-lg bg-background/55 p-2">
                      <dt className="text-muted-foreground">Token</dt>
                      <dd className="mt-1 font-mono tabular-nums">{m.total_tokens}</dd>
                    </div>
                    <div className="rounded-lg bg-background/55 p-2">
                      <dt className="text-muted-foreground">成本</dt>
                      <dd className="mt-1 font-mono tabular-nums">
                        {cost(m.estimated_cost)}
                      </dd>
                    </div>
                    <div className="rounded-lg bg-background/55 p-2">
                      <dt className="text-muted-foreground">耗时</dt>
                      <dd className="mt-1 font-mono tabular-nums">
                        {latency(m.latency_ms)}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      <Card className="hidden md:block">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>平台/用户</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>内容</TableHead>
                <TableHead>工具</TableHead>
                <TableHead>Token</TableHead>
                <TableHead>成本</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead>状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={9}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                paged.flatMap((m) => {
                  const tools = toolNames(m);
                  const expanded = expandedId === m.id;
                  return [
                    <TableRow
                      key={m.id}
                      className="cursor-pointer transition-colors hover:bg-muted/50"
                      onClick={() => setExpandedId(expanded ? null : m.id)}
                    >
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {shortTime(m.created_at)}
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">{m.platform}</div>
                        <div className="text-xs text-muted-foreground">
                          {m.user_name || m.user_id}
                        </div>
                      </TableCell>
                      <TableCell>{m.role}</TableCell>
                      <TableCell className="max-w-md whitespace-pre-wrap break-words">
                        {m.content}
                      </TableCell>
                      <TableCell className="text-primary">{tools}</TableCell>
                      <TableCell>{m.total_tokens}</TableCell>
                      <TableCell>{cost(m.estimated_cost)}</TableCell>
                      <TableCell>{latency(m.latency_ms)}</TableCell>
                      <TableCell>
                        <Badge variant={m.success ? "secondary" : "destructive"}>
                          {m.success ? "成功" : "失败"}
                        </Badge>
                      </TableCell>
                    </TableRow>,
                    expanded ? (
                      <TableRow key={`${m.id}-detail`}>
                        <TableCell colSpan={9} className="bg-muted/20 p-0">
                          <MessageDetail message={m} />
                        </TableCell>
                      </TableRow>
                    ) : null,
                  ];
                })
              )}
              {!loading && filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9}>
                    <EmptyState
                      icon={Inbox}
                      title={items.length === 0 ? "暂无对话记录" : "没有匹配的记录"}
                      description={
                        items.length === 0
                          ? "员工在 IM 中 @ 机器人后，对话会记录在这里"
                          : "试试调整搜索或筛选条件"
                      }
                    />
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-xs text-muted-foreground">
            第 {currentPage} / {totalPages} 页 · 共 {filtered.length} 条
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1}
              onClick={() => setPage(currentPage - 1)}
            >
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages}
              onClick={() => setPage(currentPage + 1)}
            >
              下一页
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
