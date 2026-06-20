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
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
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
    chunks: (id: string) => request<DocumentChunkItem[]>(`/api/admin/documents/${id}/chunks`),
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
      const response = await fetch(`${BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform: "web",
          conversation_id: "debug",
          user_id: "admin",
          message,
        }),
      });
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
