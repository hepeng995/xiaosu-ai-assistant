import { AlertCircle } from "lucide-react";

/**
 * 统一的页面级错误条（destructive 边框 + 图标 + 文案）。
 *
 * 用于页面加载失败、表单提交错误等需要常驻的错误场景；
 * 瞬时操作反馈（删除/保存成功）请用 `sonner` 的 `toast`。
 */
export function ErrorBanner({ message, className = "" }: { message: string; className?: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive ${className}`}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="break-words leading-5">{message}</span>
    </div>
  );
}
