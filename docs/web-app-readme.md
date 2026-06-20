# Web 后台说明

`apps/web` 是小苏 AI 助手的 Next.js 管理后台，用于文档管理、对话日志、系统设置和调试聊天。

## 本地开发

```bash
cd apps/web
pnpm dev
```

默认开发端口由 Next.js 决定；Docker Compose 运行时映射到宿主机 `http://localhost:3001`。

## 构建与检查

```bash
cd apps/web
pnpm lint
pnpm build
```

前端请求统一通过 `lib/api.ts`，浏览器端 API 地址来自 `NEXT_PUBLIC_API_BASE_URL`。
