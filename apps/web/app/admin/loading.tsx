import { Skeleton } from "@/components/ui/skeleton";

/** 路由级加载骨架（admin 子路由切换时显示，复用 Skeleton 视觉）。 */
export default function AdminLoading() {
  return (
    <div className="space-y-4 p-4 sm:p-6 md:p-8">
      <Skeleton className="h-16 w-full max-w-2xl" />
      <div className="space-y-3">
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
