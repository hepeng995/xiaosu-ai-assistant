"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ChatResult, type ReferenceItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError("");
    setResult({ answer: "", references: [], tool_calls: [], usage: {}, refused: false });
    try {
      const r = await api.chat.stream(input, {
        onToken: (token) =>
          setResult((prev) => ({
            answer: `${prev?.answer ?? ""}${token}`,
            references: prev?.references ?? [],
            tool_calls: prev?.tool_calls ?? [],
            usage: prev?.usage ?? {},
            refused: prev?.refused ?? false,
          })),
        onReferences: (references) =>
          setResult((prev) => ({
            answer: prev?.answer ?? "",
            references,
            tool_calls: prev?.tool_calls ?? [],
            usage: prev?.usage ?? {},
            refused: prev?.refused ?? false,
          })),
        onDone: (done) =>
          setResult((prev) => ({
            answer: prev?.answer ?? "",
            references: prev?.references ?? [],
            tool_calls: prev?.tool_calls ?? [],
            usage: prev?.usage ?? {},
            refused: done.refused,
          })),
      });
      setResult((prev) => ({ ...r, answer: prev?.answer || r.answer }));
    } catch (e) {
      setError(`请求失败: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">调试聊天</h1>
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
              <p className="whitespace-pre-wrap break-all text-sm">{result.answer}</p>
              {result.refused && (
                <p className="mt-2 text-xs text-orange-600">（已拒答：知识库无相关依据）</p>
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
