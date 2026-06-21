"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Inbox } from "lucide-react";
import { api, type DocumentItem } from "@/lib/api";
import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { PageHeader } from "@/components/admin/page-header";
import { Segmented } from "@/components/admin/segmented";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { errorMessage, fileSize } from "@/lib/format";
import { toast } from "sonner";
import { ErrorBanner } from "@/components/admin/error-banner";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<string, string> = {
  indexed: "border-success/20 bg-success/10 text-success",
  pending: "border-warning/20 bg-warning/10 text-warning",
  indexing: "border-primary/20 bg-primary/10 text-primary",
  failed: "border-destructive/20 bg-destructive/10 text-destructive",
  deleted: "border-muted-foreground/20 bg-muted text-muted-foreground",
};

const STATUS_FILTERS = [
  { value: "all", label: "全部" },
  { value: "indexed", label: "已索引" },
  { value: "processing", label: "处理中" },
  { value: "failed", label: "失败" },
];

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [confirmTarget, setConfirmTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.documents.list();
      setDocs(data.items);
    } catch (e) {
      setLoadError(errorMessage(e));
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

  // 智能轮询：仅当存在处理中的文档时每 5s 静默刷新，索引完成即停止。
  const hasPending = docs.some(
    (d) => d.status === "pending" || d.status === "indexing",
  );
  useEffect(() => {
    if (!hasPending) return;
    const timer = setInterval(() => load(), 5000);
    return () => clearInterval(timer);
  }, [hasPending, load]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const tid = toast.loading(`上传中：${file.name}…`);
    try {
      const doc = await api.documents.upload(file, true);
      if (doc.status === "indexed") {
        toast.success(`已索引：${file.name}，可在 IM 中提问`, { id: tid });
      } else if (doc.status === "failed") {
        toast.error(`索引失败：${doc.error_message ?? file.name}`, { id: tid });
      } else {
        toast.success(`已上传：${file.name}（${doc.status}）`, { id: tid });
      }
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (e) {
      toast.error(errorMessage(e), { id: tid });
    }
  };

  const doDelete = async () => {
    if (!confirmTarget) return;
    const { id, name } = confirmTarget;
    setConfirmTarget(null);
    try {
      await api.documents.remove(id);
      toast.success(`已删除：${name}`);
      load();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const handleReindex = async (id: string, name: string) => {
    const tid = toast.loading(`重新索引：${name}…`);
    try {
      await api.documents.reindex(id);
      toast.success(`已触发重新索引：${name}`, { id: tid });
      load();
    } catch (e) {
      toast.error(errorMessage(e), { id: tid });
    }
  };

  const filtered = docs.filter((d) => {
    const matchSearch =
      !search ||
      d.original_filename.toLowerCase().includes(search.toLowerCase());
    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "processing"
        ? d.status === "pending" || d.status === "indexing"
        : d.status === statusFilter);
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Knowledge · 02"
        title="文档管理"
        description="上传与维护 RAG 知识库文档"
      >
        <label
          className={cn(buttonVariants({ variant: "default" }), "cursor-pointer")}
        >
          + 上传文档
          <input
            ref={fileRef}
            type="file"
            accept=".md,.markdown,.pdf,.docx,.txt"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </PageHeader>

      <div className="grid gap-3 sm:flex sm:flex-wrap sm:items-center">
        <Input
          placeholder="搜索文件名…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-xs"
        />
        <Segmented
          options={STATUS_FILTERS}
          value={statusFilter}
          onChange={setStatusFilter}
        />
      </div>

      {loadError && <ErrorBanner message={loadError} />}

      <div className="space-y-3 md:hidden">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36" />
          ))
        ) : filtered.length === 0 ? (
          <Card>
            <CardContent className="p-4">
              <EmptyState
                icon={Inbox}
                title={docs.length === 0 ? "暂无文档" : "没有匹配的文档"}
                description={
                  docs.length === 0
                    ? "点击上方上传第一个知识库文档"
                    : "试试调整搜索或筛选条件"
                }
              />
            </CardContent>
          </Card>
        ) : (
          filtered.map((d) => (
            <Card key={d.id} className="corner-frame">
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <Link
                      className="break-words font-medium transition-colors hover:text-primary"
                      href={`/admin/documents/${d.id}`}
                    >
                      {d.original_filename}
                    </Link>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-muted-foreground">
                      <span>{d.file_type}</span>
                      <span>{fileSize(d.file_size)}</span>
                      <span>v{d.version}</span>
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn("shrink-0", STATUS_CLASS[d.status])}
                  >
                    {d.status}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    className={cn(
                      buttonVariants({ variant: "outline", size: "sm" }),
                      d.status !== "failed" && "col-span-2",
                    )}
                    href={`/admin/documents/${d.id}`}
                  >
                    查看
                  </Link>
                  {d.status === "failed" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReindex(d.id, d.original_filename)}
                    >
                      重新索引
                    </Button>
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    className="col-span-2 border-destructive/30 text-destructive hover:bg-destructive/10"
                    onClick={() =>
                      setConfirmTarget({ id: d.id, name: d.original_filename })
                    }
                  >
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Card className="hidden md:block">
        <CardHeader>
          <CardTitle>已上传文档</CardTitle>
          <CardDescription>
            支持 md / pdf / docx / txt；同名上传自动替换（version+1）
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>文件名</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                filtered.map((d) => (
                  <TableRow key={d.id} className="transition-colors hover:bg-muted/50">
                    <TableCell>{d.original_filename}</TableCell>
                    <TableCell>{d.file_type}</TableCell>
                    <TableCell>{fileSize(d.file_size)}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn(STATUS_CLASS[d.status])}>
                        {d.status}
                      </Badge>
                    </TableCell>
                    <TableCell>v{d.version}</TableCell>
                    <TableCell className="space-x-3 whitespace-nowrap">
                      <Link
                        className="text-primary hover:underline"
                        href={`/admin/documents/${d.id}`}
                      >
                        查看
                      </Link>
                      {d.status === "failed" && (
                        <Button
                          variant="link"
                          className="h-auto p-0 text-primary hover:no-underline"
                          onClick={() => handleReindex(d.id, d.original_filename)}
                        >
                          重新索引
                        </Button>
                      )}
                      <Button
                        variant="link"
                        className="h-auto p-0 text-destructive hover:no-underline"
                        onClick={() =>
                          setConfirmTarget({ id: d.id, name: d.original_filename })
                        }
                      >
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
              {!loading && filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <EmptyState
                      icon={Inbox}
                      title={docs.length === 0 ? "暂无文档" : "没有匹配的文档"}
                      description={
                        docs.length === 0
                          ? "点击右上角上传第一个知识库文档"
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

      <ConfirmDialog
        open={confirmTarget !== null}
        title="确认删除文档"
        description={
          confirmTarget
            ? `「${confirmTarget.name}」将被软删除，对应分块停用，IM 检索将不再命中。`
            : ""
        }
        confirmText="删除"
        destructive
        onConfirm={doDelete}
        onCancel={() => setConfirmTarget(null)}
      />
    </div>
  );
}
