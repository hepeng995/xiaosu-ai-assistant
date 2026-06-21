"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/admin/page-header";
import { EmptyState } from "@/components/admin/empty-state";
import { ChatBubble, type ChatMessage } from "@/components/admin/chat-bubble";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/format";
import { toast } from "sonner";

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

const EMPTY_ASSISTANT: ChatMessage = {
  role: "assistant",
  answer: "",
  references: [],
  tool_calls: [],
  usage: {},
  refused: false,
  thinking: true,
};

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const send = async (question?: string) => {
    const q = (question ?? input).trim();
    if (!q || loading) return;
    if (question && question !== input) setInput(question);

    const assistantIdx = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { ...EMPTY_ASSISTANT, thinking: false, role: "user", question: q, answer: "" },
      { ...EMPTY_ASSISTANT },
    ]);
    setInput("");
    setLoading(true);

    const updateAssistant = (updater: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) =>
        prev.map((m, i) => (i === assistantIdx ? updater(m) : m)),
      );

    try {
      const r = await api.chat.stream(q, {
        onToken: (token) =>
          updateAssistant((m) => ({ ...m, answer: m.answer + token, thinking: false })),
        onReferences: (references) => updateAssistant((m) => ({ ...m, references })),
        onDone: (done) =>
          updateAssistant((m) => ({ ...m, refused: done.refused, thinking: false })),
      });
      updateAssistant((m) => ({
        ...m,
        ...r,
        answer: m.answer || r.answer,
        thinking: false,
      }));
    } catch (e) {
      const msg = errorMessage(e);
      updateAssistant((m) => ({ ...m, answer: msg, refused: true, thinking: false }));
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Playground · 05"
        title="调试聊天"
        description="多轮对话测试 RAG 检索与工具调用（保留上下文）"
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
          placeholder="输入问题，如：员工每年有几天年假？（支持多轮追问）"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && send()}
        />
        <Button className="w-full sm:w-auto" onClick={() => send()} disabled={loading}>
          {loading ? "发送中…" : "发送"}
        </Button>
      </div>

      {messages.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="开始对话"
          description="输入问题或点击上方示例，支持多轮上下文与流式输出"
        />
      ) : (
        <div className="space-y-4">
          {messages.map((m, i) => (
            <ChatBubble key={i} message={m} />
          ))}
        </div>
      )}
    </div>
  );
}
