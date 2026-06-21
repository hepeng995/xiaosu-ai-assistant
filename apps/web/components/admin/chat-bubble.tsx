"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, Cpu } from "lucide-react";
import type { ReferenceItem } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/** 单条工具调用：可折叠展示参数 JSON。 */
function ToolCallDetail({
  call,
}: {
  call: { name: string; arguments: Record<string, unknown> };
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-border/40 bg-muted/30">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <Cpu className="h-3 w-3 shrink-0 text-primary" />
        <span className="font-mono text-primary">{call.name}</span>
        <ChevronDown
          className={`ml-auto h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words border-t border-border/40 px-3 py-2 font-mono text-[11px] leading-5 text-muted-foreground">
          {JSON.stringify(call.arguments, null, 2)}
        </pre>
      )}
    </div>
  );
}

function usageText(usage: {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
}): string | null {
  if (!usage?.total_tokens) return null;
  const parts: string[] = [];
  if (usage.prompt_tokens && usage.completion_tokens) {
    parts.push(`prompt ${usage.prompt_tokens} / completion ${usage.completion_tokens}`);
  } else {
    parts.push(`tokens ${usage.total_tokens}`);
  }
  return parts.join(" · ");
}

export interface ChatMessage {
  role: "user" | "assistant";
  question?: string;
  answer: string;
  references: ReferenceItem[];
  tool_calls: { name: string; arguments: Record<string, unknown> }[];
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  refused: boolean;
  thinking?: boolean;
}

export function ChatBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
          {message.question}
        </div>
      </div>
    );
  }
  const usage = usageText(message.usage);
  return (
    <div className="flex justify-start">
      <Card className="w-full max-w-[92%]">
        <CardContent className="space-y-3 p-4">
          {message.thinking && !message.answer ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words text-sm leading-6">
              {message.answer}
            </p>
          )}
          {message.refused && (
            <p className="text-xs text-warning">（已拒答：知识库无相关依据）</p>
          )}
          {message.tool_calls.length > 0 && (
            <div className="space-y-1.5">
              {message.tool_calls.map((t, i) => (
                <ToolCallDetail key={i} call={t} />
              ))}
            </div>
          )}
          {message.references.length > 0 && (
            <div className="space-y-1.5 border-t border-border/40 pt-2">
              <p className="text-xs text-muted-foreground">
                参考来源（{message.references.length}）
              </p>
              {message.references.map((r: ReferenceItem, i) => (
                <Link
                  key={r.chunk_id || i}
                  className="block break-words text-xs text-primary transition-colors hover:underline"
                  href={`/admin/documents/${r.document_id}?chunk=${r.chunk_id}`}
                >
                  [{i + 1}] {r.filename}
                  {r.heading_path ? `｜${r.heading_path}` : ""}
                </Link>
              ))}
            </div>
          )}
          {usage && <p className="font-mono text-[10px] text-muted-foreground">{usage}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
