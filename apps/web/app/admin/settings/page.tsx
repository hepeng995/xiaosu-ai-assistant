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
import { toast } from "sonner";
import { ErrorBanner } from "@/components/admin/error-banner";

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
  const [ragTopK, setRagTopK] = useState("");
  const [ragThreshold, setRagThreshold] = useState("");
  const [ragSaving, setRagSaving] = useState(false);

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
      setRagTopK(String(rag.top_k ?? ""));
      setRagThreshold(String(rag.score_threshold ?? ""));
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
    try {
      const d = await api.settings.putModel(modelInput.trim());
      setModelActive(d.active_model);
      toast.success(`已切换为 ${d.active_model}，新对话生效`);
    } catch {
      toast.error("保存失败，请检查模型名是否合法");
    } finally {
      setModelSaving(false);
    }
  };

  const saveRag = async () => {
    const topK = parseInt(ragTopK, 10);
    const threshold = parseFloat(ragThreshold);
    if (Number.isNaN(topK) || Number.isNaN(threshold)) {
      toast.error("请输入有效数字");
      return;
    }
    setRagSaving(true);
    try {
      await api.settings.putParams(topK, threshold);
      toast.success("RAG 参数已更新，后续检索立即生效");
      load();
    } catch {
      toast.error("保存失败（top_k 须 1-50，threshold 须 0-1）");
    } finally {
      setRagSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Settings · 04"
        title="系统设置"
        description="查看运行配置与密钥状态"
      />

      <p className="break-words text-sm text-muted-foreground">
        数据库连接：
        <span className={health === "ok" ? "text-success" : "text-destructive"}>
          {health || "检测中"}
        </span>
      </p>

      {error && <ErrorBanner message={error} />}

      <Card>
        <CardHeader className="p-4 sm:p-6">
          <CardTitle className="text-base">运行时模型（切换后新对话生效）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0 sm:p-6 sm:pt-0">
          <p className="text-sm text-muted-foreground">
            当前：
            <span className="ml-1 break-words font-medium text-foreground">
              {modelActive ?? `使用默认（${modelDefault || "—"}）`}
            </span>
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              placeholder="如 gpt-4o-mini / deepseek-chat"
              value={modelInput}
              onChange={(e) => setModelInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveModel()}
            />
            <Button
              className="w-full sm:w-auto"
              onClick={saveModel}
              disabled={modelSaving || !modelInput.trim()}
            >
              {modelSaving ? "保存中…" : "保存"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            仅切换模型名；API Key / Base URL 仍走环境变量。未配置 key 时对话走 mock。
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4 sm:p-6">
          <CardTitle className="text-base">RAG 检索参数（运行时可调，立即生效）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0 sm:p-6 sm:pt-0">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="rag-top-k" className="text-xs text-muted-foreground">
                Top K（召回数 1-50）
              </label>
              <Input
                id="rag-top-k"
                type="number"
                value={ragTopK}
                onChange={(e) => setRagTopK(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="rag-threshold" className="text-xs text-muted-foreground">
                Score 阈值（0-1）
              </label>
              <Input
                id="rag-threshold"
                type="number"
                step="0.01"
                value={ragThreshold}
                onChange={(e) => setRagThreshold(e.target.value)}
              />
            </div>
          </div>
          <Button onClick={saveRag} disabled={ragSaving}>
            {ragSaving ? "保存中…" : "保存参数"}
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))
          : groups.map((g) => (
              <Card key={g.title}>
                <CardHeader className="p-4 sm:p-6">
                  <CardTitle className="text-base text-primary">{g.title}</CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-0 sm:p-6 sm:pt-0">
                  <dl className="space-y-1 text-sm">
                    {g.items.map((it) => (
                      <div
                        key={it.label}
                        className="flex flex-col gap-1 border-b border-border/35 py-2 last:border-0 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <dt className="text-muted-foreground">{it.label}</dt>
                        <dd
                          className={`flex min-w-0 items-center gap-1.5 break-words sm:justify-end sm:text-right ${
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
