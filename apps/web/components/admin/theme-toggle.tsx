"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme, type Theme } from "@/hooks/use-theme";

const NEXT_THEME: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const THEME_LABEL: Record<Theme, string> = {
  light: "浅色",
  dark: "深色",
  system: "跟随系统",
};

const THEME_ICON: Record<Theme, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

/** 主题切换按钮：点击在 浅色 → 深色 → 跟随系统 之间循环。 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const Icon = THEME_ICON[theme];

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(NEXT_THEME[theme])}
      aria-label={`当前主题：${THEME_LABEL[theme]}，点击切换`}
      title={`主题：${THEME_LABEL[theme]}`}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
