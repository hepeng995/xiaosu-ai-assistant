import Link from "next/link";
import { Compass } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/admin/empty-state";

/** 全局 404：未匹配路由的友好提示，匹配主题视觉。 */
export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-6 p-8 text-center">
      <EmptyState
        icon={Compass}
        title="404 · 页面走丢了"
        description="你访问的页面不存在或已被移除"
      />
      <Link href="/admin" className={buttonVariants({ variant: "default" })}>
        返回概览
      </Link>
    </div>
  );
}
