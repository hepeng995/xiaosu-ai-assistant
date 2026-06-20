"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ChatResult, type ReferenceItem } from "@/lib/api";

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
    <div>
      <h1 className="mb-4 text-xl font-bold">调试聊天</h1>
      <div className="mb-4 flex gap-2">
        <input
          className="flex-1 rounded border px-3 py-2 text-sm"
          placeholder="输入问题，如：员工每年有几天年假？"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          onClick={send}
          disabled={loading}
        >
          {loading ? "发送中…" : "发送"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="space-y-3">
          <div className="rounded border bg-white p-4">
            <h3 className="mb-2 font-semibold text-gray-700">回答</h3>
            <p className="whitespace-pre-wrap break-all text-sm">{result.answer}</p>
            {result.refused && (
              <p className="mt-2 text-xs text-orange-600">（已拒答：知识库无相关依据）</p>
            )}
          </div>

          {result.references.length > 0 && (
            <div className="rounded border bg-white p-4">
              <h3 className="mb-2 font-semibold text-gray-700">
                参考来源（{result.references.length}）
              </h3>
              <ul className="space-y-1 text-sm">
                {result.references.map((r: ReferenceItem, i) => (
                  <li key={r.chunk_id || i} className="text-blue-700">
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
                    <p className="mt-1 text-xs text-gray-500">{r.quote}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.tool_calls.length > 0 && (
            <div className="rounded border bg-white p-4 text-sm">
              <span className="text-gray-500">调用工具：</span>
              {result.tool_calls.map((t, i) => (
                <span key={i} className="mr-2 rounded bg-blue-50 px-2 py-0.5 text-blue-700">
                  {t.name}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
