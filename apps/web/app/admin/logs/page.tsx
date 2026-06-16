"use client";

import { useEffect, useState } from "react";
import { api, type MessageItem } from "@/lib/api";

export default function LogsPage() {
  const [items, setItems] = useState<MessageItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    setLoading(true);
    api.messages
      .list(100)
      .then((d) => setItems(d.items))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api.messages.list(100);
        if (active) setItems(data.items);
      } catch {
        // 忽略加载错误
      }
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">对话日志</h1>
        <button onClick={refresh} className="text-sm text-blue-600 hover:underline">
          {loading ? "刷新中…" : "刷新"}
        </button>
      </div>
      <table className="w-full border-collapse bg-white text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="p-2">时间</th>
            <th className="p-2">角色</th>
            <th className="p-2">内容</th>
            <th className="p-2">工具</th>
            <th className="p-2">Token</th>
            <th className="p-2">耗时</th>
            <th className="p-2">状态</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => {
            const tools = (m.tool_calls as { name: string }[] | null)?.map((t) => t.name).join(",") ?? "";
            return (
              <tr key={m.id} className="border-b align-top">
                <td className="p-2 whitespace-nowrap text-gray-500">
                  {m.created_at?.slice(5, 16)}
                </td>
                <td className="p-2">{m.role}</td>
                <td className="p-2 max-w-md whitespace-pre-wrap break-all">{m.content}</td>
                <td className="p-2 text-blue-600">{tools}</td>
                <td className="p-2">{m.total_tokens}</td>
                <td className="p-2">{m.latency_ms ? `${m.latency_ms}ms` : "-"}</td>
                <td className="p-2">{m.success ? "✅" : "❌"}</td>
              </tr>
            );
          })}
          {items.length === 0 && (
            <tr>
              <td colSpan={7} className="p-8 text-center text-gray-400">
                暂无对话记录
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
