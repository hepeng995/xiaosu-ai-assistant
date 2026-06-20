"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocumentItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<string, string> = {
  indexed: "border-green-200 text-green-700",
  pending: "border-yellow-200 text-yellow-700",
  indexing: "border-blue-200 text-blue-700",
  failed: "border-red-200 text-red-700",
  deleted: "border-gray-200 text-gray-400",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.documents.list();
      setDocs(data.items);
    } catch (e) {
      setMsg(`加载失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api.documents.list();
        if (active) setDocs(data.items);
      } catch (e) {
        if (active) setMsg(`加载失败: ${e}`);
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(`上传中: ${file.name}，正在等待索引完成`);
    try {
      const doc = await api.documents.upload(file, true);
      if (doc.status === "indexed") {
        setMsg(`已索引: ${file.name}，现在可以在 IM 中提问`);
      } else if (doc.status === "failed") {
        setMsg(`索引失败: ${doc.error_message ?? file.name}`);
      } else {
        setMsg(`已上传: ${file.name}，当前状态 ${doc.status}`);
      }
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (err) {
      setMsg(`上传失败: ${err}`);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确认删除 ${name}？`)) return;
    await api.documents.remove(id);
    setMsg(`已删除: ${name}`);
    refresh();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">文档管理</h1>
        <label className={cn(buttonVariants({ variant: "default" }), "cursor-pointer")}>
          + 上传文档
          <input
            ref={fileRef}
            type="file"
            accept=".md,.markdown,.pdf,.docx,.txt"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </div>
      {msg && <p className="text-sm text-muted-foreground">{msg}</p>}
      <Card>
        <CardHeader>
          <CardTitle>已上传文档</CardTitle>
          <CardDescription>支持 md / pdf / docx / txt；同名上传自动替换（version+1）</CardDescription>
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
              {docs.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.original_filename}</TableCell>
                  <TableCell>{d.file_type}</TableCell>
                  <TableCell>{(d.file_size / 1024).toFixed(1)} KB</TableCell>
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
                    <Button
                      variant="link"
                      className="h-auto p-0 text-destructive hover:no-underline"
                      onClick={() => handleDelete(d.id, d.original_filename)}
                    >
                      删除
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {docs.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={6} className="p-8 text-center text-muted-foreground">
                    暂无文档
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
