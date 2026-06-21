import type { Metadata } from "next";
import { Fraunces, JetBrains_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

// 拉丁字体自托管（避免 Google CDN 阻塞国内首屏）；中文 Noto Serif SC 仍走 CDN（大字体）
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "小苏 AI 助手 · 管理后台",
  description: "公司内部 AI 助手「小苏」管理后台",
};

// 在 hydration 前同步应用主题，避免暗色模式首屏闪白。
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var t = localStorage.getItem('xiaosu-theme') || 'system';
    var dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`h-full antialiased ${fraunces.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster richColors position="top-center" closeButton toastOptions={{ duration: 3500 }} />
      </body>
    </html>
  );
}
