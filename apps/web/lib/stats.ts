import type { DocumentItem, MessageItem } from "@/lib/api";

export interface DashboardStats {
  /** 未删除文档总数。 */
  docTotal: number;
  /** 已索引文档数。 */
  docIndexed: number;
  /** 消息总数。 */
  msgTotal: number;
  /** 助手回复消息数。 */
  assistantTotal: number;
  /** 助手回复成功率（0-100）。 */
  successRate: number;
  /** 累计 token 消耗。 */
  totalTokens: number;
  /** 累计估算成本。 */
  totalCost: number;
}

/** 从已加载的消息与文档列表本地聚合出概览统计（不依赖后端聚合接口）。 */
export function summarize(
  messages: MessageItem[],
  docs: DocumentItem[],
): DashboardStats {
  const activeDocs = docs.filter((d) => d.status !== "deleted");
  const docIndexed = activeDocs.filter((d) => d.status === "indexed").length;
  const assistant = messages.filter((m) => m.role === "assistant");
  const success = assistant.filter((m) => m.success).length;
  const totalTokens = messages.reduce((sum, m) => sum + (m.total_tokens || 0), 0);
  const totalCost = messages.reduce(
    (sum, m) => sum + (m.estimated_cost || 0),
    0,
  );

  return {
    docTotal: activeDocs.length,
    docIndexed,
    msgTotal: messages.length,
    assistantTotal: assistant.length,
    successRate: assistant.length
      ? Math.round((success / assistant.length) * 100)
      : 100,
    totalTokens,
    totalCost,
  };
}
