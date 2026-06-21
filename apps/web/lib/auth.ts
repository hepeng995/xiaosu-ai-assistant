"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * 管理后台登录态：基于 localStorage 的 JWT token 存取 + 跨标签页同步。
 *
 * 设计与 use-theme.ts 一致：把 token 视作外部存储，用 useSyncExternalStore 订阅，
 * 天然 SSR 安全（服务端快照恒为 null，避免 hydration 不匹配）。
 * 401 时由 api 客户端调用 clearToken()，admin 布局监听到 token 失空即跳登录页。
 */

const TOKEN_STORAGE_KEY = "xiaosu-token";
// 同步写一份 cookie 供 middleware.ts 在 SSR 层做路由守卫（消除首屏白屏闪）
const TOKEN_COOKIE = "xiaosu-token";
const TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 天；实际鉴权仍由后端 JWT 过期校验

function writeCookie(token: string): void {
  // JWT 字符集（base64url + 点号）在 cookie 值中合法，无需 encode
  document.cookie = `${TOKEN_COOKIE}=${token}; path=/; max-age=${TOKEN_COOKIE_MAX_AGE}; SameSite=Lax`;
}

function clearCookie(): void {
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  // 跨标签页同步：其他标签页登出/登录时本页也刷新
  const onStorage = (e: StorageEvent) => {
    if (e.key === TOKEN_STORAGE_KEY) callback();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", onStorage);
  };
}

/** 读取当前 token（非 hook 场景使用，如 api 客户端注入）。 */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return readToken();
}

/** 持久化 token 并通知所有订阅者。 */
export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  writeCookie(token);
  notify();
}

/** 清除 token（登出 / 401 失效）并通知所有订阅者。 */
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  clearCookie();
  notify();
}

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  logout: () => void;
}

/** 登录态 hook：返回 token、是否已登录、登出方法。 */
export function useAuth(): AuthState {
  const token = useSyncExternalStore<string | null>(
    subscribe,
    readToken,
    () => null,
  );
  const logout = useCallback(() => clearToken(), []);
  return { token, isAuthenticated: Boolean(token), logout };
}
