"use client";

import { useEffect, useState } from "react";
import { api, type MessageItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function LogsPage() {
  const [items, setItems] = useState<MessageItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    setLoading(true);
    api.messages
      .list(100)
      .then((d) => setItems(d.items))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api.messages.list(100);
        if (active) setItems(data.items);
      } catch {
        // 忽略加载错误
      }
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">对话日志</h1>
        <Button variant="outline" size="sm" onClick={refresh}>
          {loading ? "刷新中…" : "刷新"}
        </Button>
      </div>
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
              {items.map((m) => {
                const tools =
                  (m.tool_calls as { name: string }[] | null)?.map((t) => t.name).join(",") ?? "";
                return (
                  <TableRow key={m.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {m.created_at?.slice(5, 16)}
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{m.platform}</div>
                      <div className="text-xs text-muted-foreground">{m.user_name || m.user_id}</div>
                    </TableCell>
                    <TableCell>{m.role}</TableCell>
                    <TableCell className="max-w-md whitespace-pre-wrap break-all">
                      {m.content}
                    </TableCell>
                    <TableCell className="text-primary">{tools}</TableCell>
                    <TableCell>{m.total_tokens}</TableCell>
                    <TableCell>
                      {m.estimated_cost && m.estimated_cost > 0
                        ? `$${m.estimated_cost.toFixed(4)}`
                        : "-"}
                    </TableCell>
                    <TableCell>{m.latency_ms ? `${m.latency_ms}ms` : "-"}</TableCell>
                    <TableCell>
                      <Badge variant={m.success ? "secondary" : "destructive"}>
                        {m.success ? "成功" : "失败"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="p-8 text-center text-muted-foreground">
                    暂无对话记录
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
