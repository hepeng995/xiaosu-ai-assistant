/**
 * 后端 API 客户端封装。
 * base url 来自构建期注入的 NEXT_PUBLIC_API_BASE_URL。
 */
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

export interface MessageItem {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  references: unknown[];
  tool_calls: unknown[];
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  success: boolean;
  error_code: string | null;
  latency_ms: number | null;
  created_at: string | null;
}

export interface ChatResult {
  answer: string;
  references: unknown[];
  tool_calls: { name: string; arguments: Record<string, unknown> }[];
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  refused: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`请求失败 ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; service: string }>("/health"),

  documents: {
    list: () => request<{ items: DocumentItem[]; total: number }>("/api/admin/documents"),
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return fetch(`${BASE_URL}/api/admin/documents`, { method: "POST", body: form }).then((r) => {
        if (!r.ok) throw new Error("上传失败");
        return r.json() as Promise<DocumentItem>;
      });
    },
    remove: (id: string) =>
      request<{ success: boolean }>(`/api/admin/documents/${id}`, { method: "DELETE" }),
  },

  messages: {
    list: (limit = 50) =>
      request<{ items: MessageItem[]; total: number }>(`/api/admin/messages?limit=${limit}`),
  },

  settings: {
    get: () => request<Record<string, unknown>>("/api/admin/settings"),
    health: () => request<{ database: string; service: string }>("/api/admin/settings/health"),
  },

  chat: {
    send: (message: string) =>
      request<ChatResult>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ platform: "web", conversation_id: "debug", user_id: "admin", message }),
      }),
  },
};
