"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, type DocumentChunkItem } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">文档分块预览</h1>
        <Link className={cn(buttonVariants({ variant: "outline", size: "sm" }))} href="/admin/documents">
          返回文档列表
        </Link>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-3">
        {chunks.map((chunk) => {
          const active = chunk.id === targetChunk;
          return (
            <Card
              id={`chunk-${chunk.id}`}
              key={chunk.id}
              className={active ? "border-primary ring-2 ring-primary/20" : ""}
            >
              <CardContent className="pt-6">
                <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span>{chunkLocation(chunk)}</span>
                  <span>#{chunk.chunk_index}</span>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm leading-6">
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
