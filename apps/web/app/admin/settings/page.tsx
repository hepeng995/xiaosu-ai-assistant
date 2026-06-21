"use client";

import { useCallback, useEffect, useState } from "react";
import { CircleCheck, CircleX } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/admin/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/format";

interface SettingItem {
  label: string;
  value: string;
  ok?: boolean;
}

interface SettingGroup {
  title: string;
  items: SettingItem[];
}

export default function SettingsPage() {
  const [groups, setGroups] = useState<SettingGroup[]>([]);
  const [health, setHealth] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modelActive, setModelActive] = useState<string | null>(null);
  const [modelDefault, setModelDefault] = useState<string>("");
  const [modelInput, setModelInput] = useState("");
  const [modelSaving, setModelSaving] = useState(false);
  const [modelMsg, setModelMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.settings.get();
      const llm = data.llm as Record<string, unknown>;
      const emb = data.embedding as Record<string, unknown>;
      const rag = data.rag as Record<string, unknown>;
      const dt = data.dingtalk as Record<string, unknown>;
      const fs = data.feishu as Record<string, unknown>;
      const ag = data.agent as Record<string, unknown>;
      const obs = data.observability as Record<string, unknown>;
      setGroups([
        {
          title: "LLM 模型",
          items: [
            { label: "Provider", value: String(llm.provider) },
            { label: "模型", value: String(llm.model) },
            {
              label: "API Key",
              value: llm.api_key_configured ? "已配置" : "未配置",
              ok: Boolean(llm.api_key_configured),
            },
          ],
        },
        {
          title: "Embedding",
          items: [
            { label: "模型", value: String(emb.model) },
            { label: "维度", value: String(emb.dimension) },
            {
              label: "API Key",
              value: emb.api_key_configured ? "已配置" : "未配置",
              ok: Boolean(emb.api_key_configured),
            },
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
            {
              label: "App Key",
              value: dt.app_key_configured ? "已配置" : "未配置",
              ok: Boolean(dt.app_key_configured),
            },
            {
              label: "App Secret",
              value: dt.app_secret_configured ? "已配置" : "未配置",
              ok: Boolean(dt.app_secret_configured),
            },
            {
              label: "Robot Code",
              value: dt.robot_code_configured ? "已配置" : "未配置",
              ok: Boolean(dt.robot_code_configured),
            },
          ],
        },
        {
          title: "飞书 IM",
          items: [
            {
              label: "App ID",
              value: fs.app_id_configured ? "已配置" : "未配置",
              ok: Boolean(fs.app_id_configured),
            },
            {
              label: "App Secret",
              value: fs.app_secret_configured ? "已配置" : "未配置",
              ok: Boolean(fs.app_secret_configured),
            },
            {
              label: "Verification Token",
              value: fs.verification_token_configured ? "已配置" : "未配置",
              ok: Boolean(fs.verification_token_configured),
            },
            {
              label: "Encrypt Key",
              value: fs.encrypt_key_configured ? "已配置" : "未配置",
              ok: Boolean(fs.encrypt_key_configured),
            },
          ],
        },
        {
          title: "Agent",
          items: [
            { label: "最大工具轮数", value: String(ag.max_tool_rounds) },
            { label: "工具超时", value: `${ag.tool_timeout}s` },
          ],
        },
        {
          title: "可观测性",
          items: [
            {
              label: "Langfuse",
              value: obs.langfuse_enabled ? "已启用" : "未配置",
              ok: Boolean(obs.langfuse_enabled),
            },
            {
              label: "Host",
              value: obs.host_configured ? "已配置" : "未配置",
              ok: Boolean(obs.host_configured),
            },
          ],
        },
      ]);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
    api.settings
      .health()
      .then((h) => setHealth(h.database))
      .catch(() => setHealth("unknown"));
    api.settings
      .getModel()
      .then((d) => {
        setModelActive(d.active_model);
        setModelDefault(d.default_model);
        setModelInput(d.active_model ?? "");
      })
      .catch(() => {
        // 忽略模型读取错误，保持默认占位
      });
  }, []);

  useEffect(() => {
    const run = async () => {
      await load();
    };
    run();
  }, [load]);

  const saveModel = async () => {
    if (!modelInput.trim()) return;
    setModelSaving(true);
    setModelMsg(null);
    try {
      const d = await api.settings.putModel(modelInput.trim());
      setModelActive(d.active_model);
      setModelMsg({ ok: true, text: `已切换为 ${d.active_model}，新对话生效` });
    } catch {
      setModelMsg({ ok: false, text: "保存失败，请检查模型名是否合法" });
    } finally {
      setModelSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Settings · 04"
        title="系统设置"
        description="查看运行配置与密钥状态"
      />

      <p className="text-sm text-muted-foreground">
        数据库连接：
        <span className={health === "ok" ? "text-success" : "text-destructive"}>
          {health || "检测中"}
        </span>
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">运行时模型（切换后新对话生效）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            当前：
            <span className="ml-1 font-medium text-foreground">
              {modelActive ?? `使用默认（${modelDefault || "—"}）`}
            </span>
          </p>
          <div className="flex gap-2">
            <Input
              placeholder="如 gpt-4o-mini / deepseek-chat"
              value={modelInput}
              onChange={(e) => setModelInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveModel()}
            />
            <Button onClick={saveModel} disabled={modelSaving || !modelInput.trim()}>
              {modelSaving ? "保存中…" : "保存"}
            </Button>
          </div>
          {modelMsg && (
            <p className={`text-sm ${modelMsg.ok ? "text-success" : "text-destructive"}`}>
              {modelMsg.text}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            仅切换模型名；API Key / Base URL 仍走环境变量。未配置 key 时对话走 mock。
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))
          : groups.map((g) => (
              <Card key={g.title}>
                <CardHeader>
                  <CardTitle className="text-base text-primary">{g.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-1 text-sm">
                    {g.items.map((it) => (
                      <div key={it.label} className="flex items-center justify-between">
                        <dt className="text-muted-foreground">{it.label}</dt>
                        <dd
                          className={`flex items-center gap-1.5 ${
                            it.ok === false
                              ? "text-destructive"
                              : it.ok
                                ? "text-success"
                                : ""
                          }`}
                        >
                          {it.ok === true && <CircleCheck className="h-3.5 w-3.5" />}
                          {it.ok === false && <CircleX className="h-3.5 w-3.5" />}
                          {it.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            ))}
      </div>
    </div>
  );
}
