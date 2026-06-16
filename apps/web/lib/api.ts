/**
 * 后端 API 客户端封装。
 *
 * base url 来自构建期注入的环境变量 NEXT_PUBLIC_API_BASE_URL。
 * 统一处理错误体：{ success, error_code, message, trace_id }。
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** 后端统一错误体。 */
interface ApiErrorResponse {
  success: false;
  error_code: string;
  message: string;
  trace_id?: string;
}

/** 解析后端错误并抛出 ApiError。 */
export class ApiError extends Error {
  errorCode: string;
  traceId: string | undefined;
  status: number;

  constructor(errorCode: string, message: string, traceId: string | undefined, status: number) {
    super(message);
    this.name = "ApiError";
    this.errorCode = errorCode;
    this.traceId = traceId;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    let body: ApiErrorResponse | null = null;
    try {
      body = (await response.json()) as ApiErrorResponse;
    } catch {
      // 非 JSON 错误体，忽略
    }
    throw new ApiError(
      body?.error_code ?? "UNKNOWN_ERROR",
      body?.message ?? "请求失败，请稍后再试",
      body?.trace_id,
      response.status,
    );
  }

  return (await response.json()) as T;
}

export interface HealthResponse {
  status: string;
  service: string;
}

/** 后端 API 调用入口。 */
export const api = {
  health: () => request<HealthResponse>("/health"),
};
