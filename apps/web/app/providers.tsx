"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * 全局 Provider 包装：React Query（缓存 / 重试 / stale-while-revalidate）。
 *
 * 引入后各页面可逐步将手写 useEffect+fetch 迁移到 useQuery，获得自动缓存与重试。
 * 默认 staleTime 30s（避免频繁请求），retry 1 次，不在窗口聚焦时自动刷新。
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
