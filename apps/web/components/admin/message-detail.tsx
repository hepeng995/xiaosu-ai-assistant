import type { MessageItem, ReferenceItem } from "@/lib/api";

/**
 * 消息详情展开：显示完整 tool_calls（参数/返回）、references、token 拆分。
 * 用于对话日志点击单条消息后展开查看。
 */
export function MessageDetail({ message }: { message: MessageItem }) {
  const tools =
    (message.tool_calls as
      | { name: string; arguments?: unknown; result?: unknown }[]
      | null) ?? [];
  const refs = (message.references as ReferenceItem[] | null) ?? [];
  return (
    <div className="space-y-3 bg-muted/20 px-4 py-3 text-sm">
      <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground">
        <span>prompt {message.prompt_tokens}</span>
        <span>completion {message.completion_tokens}</span>
        <span>total {message.total_tokens}</span>
        {message.error_code && (
          <span className="text-destructive">错误码 {message.error_code}</span>
        )}
      </div>

      {tools.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">工具调用（{tools.length}）</p>
          {tools.map((t, i) => (
            <div
              key={i}
              className="rounded-md border border-border/40 bg-background/60 p-2"
            >
              <p className="font-mono text-xs text-primary">{t.name}</p>
              {t.arguments !== undefined && (
                <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted-foreground">
                  参数：{JSON.stringify(t.arguments, null, 2)}
                </pre>
              )}
              {t.result !== undefined && (
                <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted-foreground">
                  返回：{JSON.stringify(t.result, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {refs.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">引用来源（{refs.length}）</p>
          {refs.map((r, i) => (
            <div
              key={i}
              className="rounded-md border border-border/40 bg-background/60 p-2"
            >
              <p className="break-words text-xs text-primary">
                {r.filename}
                {r.heading_path ? `｜${r.heading_path}` : ""}
              </p>
              {r.quote && (
                <p className="mt-1 whitespace-pre-wrap break-words text-[11px] leading-5 text-muted-foreground">
                  {r.quote}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
