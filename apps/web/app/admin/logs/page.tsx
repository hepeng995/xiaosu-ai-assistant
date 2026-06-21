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

export default function LogsPage() {
  const [items, setItems] = useState<MessageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [refreshing, setRefreshing] = useState(false);

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

  return (
    <div className="space-y-4">
      <PageHeader title="对话日志" description="查看历史对话、工具调用与 Token 消耗">
        <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
          {refreshing ? "刷新中…" : "刷新"}
        </Button>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="搜索内容或用户…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
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

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
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
                filtered.map((m) => {
                  const tools =
                    (m.tool_calls as { name: string }[] | null)
                      ?.map((t) => t.name)
                      .join(",") ?? "";
                  return (
                    <TableRow key={m.id} className="transition-colors hover:bg-muted/50">
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
                      <TableCell className="max-w-md whitespace-pre-wrap break-all">
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
                    </TableRow>
                  );
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
    </div>
  );
}
