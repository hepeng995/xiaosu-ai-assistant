"use client";

import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { errorMessage } from "@/lib/format";

/** 页面级错误边界：捕获 React 渲染异常，提供重试与返回入口。 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <AlertCircle className="h-12 w-12 text-destructive" />
      <div className="space-y-1">
        <h2 className="font-display text-xl">页面出错了</h2>
        <p className="break-words text-sm text-muted-foreground">
          {errorMessage(error)}
        </p>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={reset}>
          重试
        </Button>
        <Link href="/admin" className={buttonVariants({ variant: "default" })}>
          返回概览
        </Link>
      </div>
    </div>
  );
}
