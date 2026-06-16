"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface SettingGroup {
  title: string;
  items: { label: string; value: string; ok?: boolean }[];
}

export default function SettingsPage() {
  const [groups, setGroups] = useState<SettingGroup[]>([]);
  const [health, setHealth] = useState<string>("");

  useEffect(() => {
    api.settings.get().then((data) => {
      const llm = data.llm as Record<string, unknown>;
      const emb = data.embedding as Record<string, unknown>;
      const rag = data.rag as Record<string, unknown>;
      const dt = data.dingtalk as Record<string, unknown>;
      const ag = data.agent as Record<string, unknown>;
      setGroups([
        {
          title: "LLM 模型",
          items: [
            { label: "Provider", value: String(llm.provider) },
            { label: "模型", value: String(llm.model) },
            { label: "API Key", value: llm.api_key_configured ? "已配置" : "未配置", ok: Boolean(llm.api_key_configured) },
          ],
        },
        {
          title: "Embedding",
          items: [
            { label: "模型", value: String(emb.model) },
            { label: "维度", value: String(emb.dimension) },
            { label: "API Key", value: emb.api_key_configured ? "已配置" : "未配置", ok: Boolean(emb.api_key_configured) },
          ],
        },
        {
          title: "RAG",
          items: [
            { label: "Top K", value: String(rag.top_k) },
            { label: "阈值", value: String(rag.score_threshold) },
            { label: "分块大小", value: String(rag.chunk_size) },
          ],
        },
        {
          title: "钉钉 IM",
          items: [
            { label: "App Key", value: dt.app_key_configured ? "已配置" : "未配置", ok: Boolean(dt.app_key_configured) },
            { label: "App Secret", value: dt.app_secret_configured ? "已配置" : "未配置", ok: Boolean(dt.app_secret_configured) },
            { label: "Robot Code", value: dt.robot_code_configured ? "已配置" : "未配置", ok: Boolean(dt.robot_code_configured) },
          ],
        },
        {
          title: "Agent",
          items: [
            { label: "最大工具轮数", value: String(ag.max_tool_rounds) },
            { label: "工具超时", value: `${ag.tool_timeout}s` },
          ],
        },
      ]);
    });
    api.settings.health().then((h) => setHealth(h.database));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">系统设置</h1>
      <p className="mb-4 text-sm text-gray-600">
        数据库连接：<span className={health === "ok" ? "text-green-600" : "text-red-600"}>{health || "检测中"}</span>
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {groups.map((g) => (
          <div key={g.title} className="rounded border bg-white p-4">
            <h2 className="mb-3 font-semibold text-blue-700">{g.title}</h2>
            <dl className="space-y-1 text-sm">
              {g.items.map((it) => (
                <div key={it.label} className="flex justify-between">
                  <dt className="text-gray-500">{it.label}</dt>
                  <dd className={it.ok === false ? "text-red-500" : it.ok ? "text-green-600" : ""}>
                    {it.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
