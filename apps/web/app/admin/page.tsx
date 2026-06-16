/**
 * 管理后台首页（第 1 阶段占位）。
 * 后续阶段将接入：文档管理 / 对话日志 / 系统设置 / 调试聊天。
 */
export default function AdminPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-bold tracking-tight">小苏 AI 助手 · 管理后台</h1>
      <p className="text-gray-500">
        第 1 阶段骨架占位页。后续将接入文档管理 / 对话日志 / 系统设置 / 调试聊天。
      </p>
    </main>
  );
}
