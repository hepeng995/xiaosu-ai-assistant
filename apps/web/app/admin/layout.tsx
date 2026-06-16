import Link from "next/link";

const NAV_ITEMS = [
  { href: "/admin/documents", label: "文档管理" },
  { href: "/admin/logs", label: "对话日志" },
  { href: "/admin/settings", label: "系统设置" },
  { href: "/admin/chat", label: "调试聊天" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-56 shrink-0 border-r border-gray-200 bg-white p-4">
        <h2 className="mb-6 text-lg font-bold text-blue-700">小苏后台</h2>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
