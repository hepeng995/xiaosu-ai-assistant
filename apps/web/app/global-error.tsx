"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";

/**
 * 根级错误边界：替代 root layout，必须自含 <html><body>。
 * 全局样式此时可能未加载，故使用 inline style，不依赖 Tailwind。
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 上报到日志（占位，未配置可观测性时仅 console）
    console.error(error);
  }, [error]);

  return (
    <html lang="zh-CN">
      <body>
        <div
          style={{
            display: "flex",
            minHeight: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            padding: 32,
            textAlign: "center",
            fontFamily: "system-ui, -apple-system, 'PingFang SC', sans-serif",
            color: "#1a1a1a",
            background: "#fafafa",
          }}
        >
          <AlertCircle size={48} color="#dc2626" />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>系统发生错误</h2>
          <p style={{ margin: 0, color: "#666", fontSize: 14 }}>
            {error.message || "未知错误，请稍后重试"}
          </p>
          <button
            onClick={() => reset()}
            style={{
              padding: "8px 20px",
              border: "1px solid #ccc",
              borderRadius: 8,
              background: "transparent",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            重试
          </button>
        </div>
      </body>
    </html>
  );
}
