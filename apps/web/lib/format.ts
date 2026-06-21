/** 展示层格式化工具：文件大小 / 成本 / 耗时 / 时间 / 友好错误。 */

/** 字节数转可读大小（B / KB / MB）。 */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 估算成本，0 或空显示占位符。 */
export function cost(value: number | null | undefined): string {
  return value && value > 0 ? `$${value.toFixed(4)}` : "-";
}

/** 毫秒耗时，空显示占位符。 */
export function latency(ms: number | null | undefined): string {
  return ms ? `${ms}ms` : "-";
}

/** ISO 时间截取为 "MM-DD HH:mm"。 */
export function shortTime(iso: string | null | undefined): string {
  return iso ? iso.slice(5, 16) : "-";
}

/**
 * 把任意异常转成对用户友好的中文文案，避免把技术细节（如 "Error: ..."）抛给用户。
 * fetch 网络层失败在浏览器表现为 TypeError；api 客户端抛出的已是中文友好文案。
 */
export function errorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    return "无法连接服务，请确认后端服务已启动";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "操作失败，请稍后再试";
}
