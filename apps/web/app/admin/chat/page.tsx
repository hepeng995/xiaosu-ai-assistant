"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ChatResult, type ReferenceItem } from "@/lib/api";
import { PageHeader } from "@/components/admin/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/format";

const EMPTY_RESULT: ChatResult = {
  answer: "",
  references: [],
  tool_calls: [],
  usage: {},
  refused: false,
};

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError("");
    setResult({ ...EMPTY_RESULT });
    try {
      const r = await api.chat.stream(input, {
        onToken: (token) =>
          setResult((prev) => ({
            ...(prev ?? EMPTY_RESULT),
            answer: `${prev?.answer ?? ""}${token}`,
          })),
        onReferences: (references) =>
          setResult((prev) => ({ ...(prev ?? EMPTY_RESULT), references })),
        onDone: (done) =>
          setResult((prev) => ({ ...(prev ?? EMPTY_RESULT), refused: done.refused })),
      });
      setResult((prev) => ({ ...r, answer: prev?.answer || r.answer }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const thinking = loading && !result?.answer;

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Playground · 05"
        title="调试聊天"
        description="在 Web 端测试 RAG 检索与工具调用"
      />
      <div className="flex gap-2">
        <Input
          placeholder="输入问题，如：员工每年有几天年假？"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <Button onClick={send} disabled={loading}>
          {loading ? "发送中…" : "发送"}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {result && (
        <div className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">回答</CardTitle>
            </CardHeader>
            <CardContent>
              {thinking ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              ) : (
                <p className="whitespace-pre-wrap break-all text-sm">{result.answer}</p>
              )}
              {result.refused && (
                <p className="mt-2 text-xs text-warning">（已拒答：知识库无相关依据）</p>
              )}
            </CardContent>
          </Card>

          {result.references.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">参考来源（{result.references.length}）</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-sm">
                  {result.references.map((r: ReferenceItem, i) => (
                    <li key={r.chunk_id || i} className="text-primary">
                      <Link
                        className="hover:underline"
                        href={`/admin/documents/${r.document_id}?chunk=${r.chunk_id}`}
                      >
                        [{i + 1}] {r.filename}
                        {r.heading_path ? `｜${r.heading_path}` : ""}
                        {r.page_number ? `｜第 ${r.page_number} 页` : ""}
                        {r.paragraph_index !== null && r.paragraph_index !== undefined
                          ? `｜第 ${r.paragraph_index} 段`
                          : ""}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground">{r.quote}</p>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {result.tool_calls.length > 0 && (
            <Card>
              <CardContent className="pt-6 text-sm">
                <span className="text-muted-foreground">调用工具：</span>
                {result.tool_calls.map((t, i) => (
                  <span
                    key={i}
                    className="mr-2 rounded bg-secondary px-2 py-0.5 text-secondary-foreground"
                  >
                    {t.name}
                  </span>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
