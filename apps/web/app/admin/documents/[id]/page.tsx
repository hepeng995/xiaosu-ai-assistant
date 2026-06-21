"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api, type DocumentChunkItem } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/admin/page-header";
import { cn } from "@/lib/utils";

function chunkLocation(chunk: DocumentChunkItem) {
  if (chunk.heading_path) return chunk.heading_path;
  if (chunk.page_number !== null) return `第 ${chunk.page_number} 页`;
  if (chunk.paragraph_index !== null) return `第 ${chunk.paragraph_index} 段`;
  return `分块 ${chunk.chunk_index}`;
}

export default function DocumentChunksPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const targetChunk = searchParams.get("chunk");
  const [chunks, setChunks] = useState<DocumentChunkItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.documents
      .chunks(params.id)
      .then(setChunks)
      .catch((err: unknown) => setError(`加载失败: ${err}`));
  }, [params.id]);

  useEffect(() => {
    if (!targetChunk || chunks.length === 0) return;
    const target = document.getElementById(`chunk-${targetChunk}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [chunks, targetChunk]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Knowledge · 02"
        title="文档分块预览"
        description="查看该文档被切分后的知识块与定位信息"
      >
        <Link
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          href="/admin/documents"
        >
          <ArrowLeft className="h-4 w-4" />
          返回列表
        </Link>
      </PageHeader>

      {error && (
        <p className="rounded-lg border border-destructive/25 bg-destructive/8 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="space-y-3">
        {chunks.map((chunk) => {
          const active = chunk.id === targetChunk;
          return (
            <Card
              id={`chunk-${chunk.id}`}
              key={chunk.id}
              className={cn(
                "corner-frame",
                active && "border-primary ring-2 ring-primary/20",
              )}
            >
              <CardContent className="pt-6">
                <div className="mb-3 flex items-center justify-between gap-3 border-b border-border/50 pb-2">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-primary/80">
                    {chunkLocation(chunk)}
                  </span>
                  <span className="font-mono text-[11px] tabular-nums text-muted-foreground/60">
                    #{String(chunk.chunk_index).padStart(3, "0")}
                  </span>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm leading-7 text-foreground/90">
                  {chunk.content}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {chunks.length === 0 && !error && (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            暂无分块
          </CardContent>
        </Card>
      )}
    </div>
  );
}
