"use client";

import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "xiaosu-theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** 把主题落实到 <html> 的 .dark class 上。 */
function applyTheme(theme: Theme): void {
  const dark = theme === "dark" || (theme === "system" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
}

function getStoredTheme(): Theme {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" || stored === "system"
    ? stored
    : "system";
}

// 把主题视作一个外部存储，用 useSyncExternalStore 订阅，天然 SSR 安全、无 set-state-in-effect。
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  const mql = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystemChange = () => {
    applyTheme(getStoredTheme());
    callback();
  };
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      applyTheme(getStoredTheme());
      callback();
    }
  };
  mql.addEventListener("change", onSystemChange);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(callback);
    mql.removeEventListener("change", onSystemChange);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * 主题三态（浅色 / 深色 / 跟随系统）。
 * 首屏的 class 由 app/layout.tsx 的内联脚本同步应用（防闪白）；
 * 本 hook 通过 useSyncExternalStore 读取当前主题、切换并持久化，
 * 并在 system 模式下跟随系统、跨标签页同步。
 */
export function useTheme() {
  const theme = useSyncExternalStore<Theme>(
    subscribe,
    getStoredTheme,
    () => "system",
  );

  const setTheme = useCallback((next: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
    notify();
  }, []);

  return { theme, setTheme };
}
