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
import { toast } from "sonner";

const EMPTY_RESULT: ChatResult = {
  answer: "",
  references: [],
  tool_calls: [],
  usage: {},
  refused: false,
};

// 提问示例（覆盖知识库问答 / 工具调用 / 拒答边界，方便演示与自测）
const EXAMPLE_GROUPS: { title: string; items: { label: string; question: string }[] }[] = [
  {
    title: "📚 知识库问答",
    items: [
      { label: "年假天数", question: "员工每年有几天年假？" },
      { label: "报销材料", question: "报销发票需要什么材料？" },
      { label: "入职流程", question: "新人入职第一天要做哪些事？" },
      { label: "竞业限制", question: "竞业限制期限最长是多久？" },
    ],
  },
  {
    title: "🔧 工具调用",
    items: [
      { label: "员工 001", question: "员工 001 是哪个部门的？" },
      { label: "上周订单", question: "上周一共多少订单？" },
      { label: "现在时间", question: "现在几点？" },
    ],
  },
  {
    title: "🚫 拒答边界",
    items: [
      { label: "CEO 住址", question: "我们公司 CEO 的家庭住址是？" },
      { label: "2030 目标", question: "2030 年的销售目标是多少？" },
    ],
  },
];

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [loading, setLoading] = useState(false);

  const send = async (question?: string) => {
    const q = (question ?? input).trim();
    if (!q) return;
    if (question && question !== input) setInput(question);
    setLoading(true);
    setResult({ ...EMPTY_RESULT });
    try {
      const r = await api.chat.stream(q, {
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
      toast.error(errorMessage(e));
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

      <div className="space-y-3">
        {EXAMPLE_GROUPS.map((group) => (
          <div key={group.title} className="space-y-1.5">
            <p className="text-xs text-muted-foreground">{group.title}</p>
            <div className="flex flex-wrap gap-2">
              {group.items.map((item) => (
                <Button
                  key={item.label}
                  variant="outline"
                  size="sm"
                  onClick={() => send(item.question)}
                  disabled={loading}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          placeholder="输入问题，如：员工每年有几天年假？"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <Button className="w-full sm:w-auto" onClick={() => send()} disabled={loading}>
          {loading ? "发送中…" : "发送"}
        </Button>
      </div>

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
                <p className="whitespace-pre-wrap break-words text-sm leading-6">
                  {result.answer}
                </p>
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
                <ul className="space-y-3 text-sm">
                  {result.references.map((r: ReferenceItem, i) => (
                    <li key={r.chunk_id || i} className="break-words text-primary">
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
                      <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-5 text-muted-foreground">
                        {r.quote}
                      </p>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {result.tool_calls.length > 0 && (
            <Card>
              <CardContent className="flex flex-wrap gap-2 pt-6 text-sm">
                <span className="text-muted-foreground">调用工具：</span>
                {result.tool_calls.map((t, i) => (
                  <span
                    key={i}
                    className="break-words rounded bg-secondary px-2 py-0.5 text-secondary-foreground"
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
