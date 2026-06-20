"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, type DocumentChunkItem } from "@/lib/api";

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
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">文档分块预览</h1>
        <Link className="text-sm text-blue-600 hover:underline" href="/admin/documents">
          返回文档列表
        </Link>
      </div>

      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

      <div className="space-y-3">
        {chunks.map((chunk) => {
          const active = chunk.id === targetChunk;
          return (
            <section
              id={`chunk-${chunk.id}`}
              key={chunk.id}
              className={`rounded border bg-white p-4 ${
                active ? "border-blue-500 ring-2 ring-blue-100" : "border-gray-200"
              }`}
            >
              <div className="mb-2 flex items-center justify-between gap-3 text-xs text-gray-500">
                <span>{chunkLocation(chunk)}</span>
                <span>#{chunk.chunk_index}</span>
              </div>
              <p className="whitespace-pre-wrap break-words text-sm leading-6 text-gray-800">
                {chunk.content}
              </p>
            </section>
          );
        })}
      </div>

      {chunks.length === 0 && !error && (
        <p className="rounded border bg-white p-8 text-center text-sm text-gray-400">
          暂无分块
        </p>
      )}
    </div>
  );
}
