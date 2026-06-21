/**
 * 后端 API 客户端封装。
 * base url 来自构建期注入的 NEXT_PUBLIC_API_BASE_URL。
 * 所有 admin 请求自动注入 JWT（Authorization: Bearer）；401 时清除 token 触发跳登录。
 */
import { clearToken, getToken } from "@/lib/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface DocumentItem {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  status: string;
  version: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  heading_path: string | null;
  page_number: number | null;
  paragraph_index: number | null;
}

export interface MessageItem {
  id: string;
  conversation_id: string;
  platform: string;
  user_id: string;
  user_name: string | null;
  conversation_key: string;
  role: string;
  content: string;
  references: unknown[];
  tool_calls: unknown[];
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  success: boolean;
  error_code: string | null;
  latency_ms: number | null;
  created_at: string | null;
}

export interface ReferenceItem {
  document_id: string;
  chunk_id: string;
  filename: string;
  heading_path?: string | null;
  page_number?: number | null;
  paragraph_index?: number | null;
  quote: string;
  score: number;
}

export interface ChatResult {
  answer: string;
  references: ReferenceItem[];
  tool_calls: { name: string; arguments: Record<string, unknown> }[];
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  refused: boolean;
}

interface StreamHandlers {
  onToken?: (token: string) => void;
  onReferences?: (references: ReferenceItem[]) => void;
  onDone?: (done: { success: boolean; refused: boolean }) => void;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  // 401：token 缺失/过期/无效，清除后由 admin 守卫跳登录
  if (response.status === 401) {
    clearToken();
    throw new Error("登录已过期，请重新登录");
  }
  if (!response.ok) {
    throw new Error(`请求失败 ${response.status}`);
  }
  return (await response.json()) as T;
}

function parseSseBlock(block: string): { event: string; data: Record<string, unknown> } | null {
  const eventLine = block.split("\n").find((line) => line.startsWith("event:"));
  const dataLine = block.split("\n").find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;
  const event = eventLine.replace("event:", "").trim();
  const rawData = dataLine.replace("data:", "").trim();
  const parsed = JSON.parse(rawData) as Record<string, unknown>;
  return { event, data: parsed };
}

function referenceList(value: unknown): ReferenceItem[] {
  return Array.isArray(value) ? (value as ReferenceItem[]) : [];
}

export const api = {
  health: () => request<{ status: string; service: string }>("/health"),

  auth: {
    login: (username: string, password: string) =>
      request<{
        access_token: string;
        token_type: string;
        expires_in: number;
        username: string;
      }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    me: () => request<{ username: string; role: string }>("/api/auth/me"),
  },

  documents: {
    list: () => request<{ items: DocumentItem[]; total: number }>("/api/admin/documents"),
    upload: (file: File, waitForIndex = false) => {
      const form = new FormData();
      form.append("file", file);
      const search = waitForIndex ? "?wait_for_index=true" : "";
      const uploadHeaders: Record<string, string> = {};
      const uploadToken = getToken();
      if (uploadToken) uploadHeaders["Authorization"] = `Bearer ${uploadToken}`;
      return fetch(`${BASE_URL}/api/admin/documents${search}`, {
        method: "POST",
        body: form,
        headers: uploadHeaders,
      }).then((r) => {
        if (r.status === 401) {
          clearToken();
          throw new Error("登录已过期，请重新登录");
        }
        if (!r.ok) throw new Error("上传失败");
        return r.json() as Promise<DocumentItem>;
      });
    },
    remove: (id: string) =>
      request<{ success: boolean }>(`/api/admin/documents/${id}`, { method: "DELETE" }),
    chunks: (id: string) => request<DocumentChunkItem[]>(`/api/admin/documents/${id}/chunks`),
    reindex: (id: string) =>
      request<DocumentItem>(`/api/admin/documents/${id}/reindex`, { method: "POST" }),
  },

  messages: {
    list: (limit = 50) =>
      request<{ items: MessageItem[]; total: number }>(`/api/admin/messages?limit=${limit}`),
  },

  settings: {
    get: () => request<Record<string, unknown>>("/api/admin/settings"),
    health: () => request<{ database: string; service: string }>("/api/admin/settings/health"),
    getModel: () =>
      request<{ active_model: string | null; default_model: string }>(
        "/api/admin/settings/model",
      ),
    putModel: (model: string) =>
      request<{ active_model: string; default_model: string }>(
        "/api/admin/settings/model",
        { method: "PUT", body: JSON.stringify({ model }) },
      ),
  },

  chat: {
    send: (message: string) =>
      request<ChatResult>("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          platform: "web",
          conversation_id: "debug",
          user_id: "admin",
          message,
        }),
      }),
    stream: async (message: string, handlers: StreamHandlers = {}): Promise<ChatResult> => {
      const streamHeaders: Record<string, string> = { "Content-Type": "application/json" };
      const streamToken = getToken();
      if (streamToken) streamHeaders["Authorization"] = `Bearer ${streamToken}`;
      const response = await fetch(`${BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: streamHeaders,
        body: JSON.stringify({
          platform: "web",
          conversation_id: "debug",
          user_id: "admin",
          message,
        }),
      });
      if (response.status === 401) {
        clearToken();
        throw new Error("登录已过期，请重新登录");
      }
      if (!response.ok || !response.body) {
        throw new Error(`请求失败 ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      let references: ReferenceItem[] = [];
      let refused = false;

      const consume = (block: string) => {
        const parsed = parseSseBlock(block);
        if (!parsed) return;
        if (parsed.event === "token") {
          const token = typeof parsed.data.content === "string" ? parsed.data.content : "";
          answer += token;
          handlers.onToken?.(token);
        }
        if (parsed.event === "references") {
          references = referenceList(parsed.data.references);
          handlers.onReferences?.(references);
        }
        if (parsed.event === "done") {
          refused = Boolean(parsed.data.refused);
          handlers.onDone?.({ success: Boolean(parsed.data.success), refused });
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        blocks.forEach(consume);
      }
      if (buffer.trim()) consume(buffer);

      return { answer, references, tool_calls: [], usage: {}, refused };
    },
  },
};
