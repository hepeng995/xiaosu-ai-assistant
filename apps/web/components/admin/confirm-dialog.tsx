"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  /** 确认按钮是否使用危险（红色）样式，删除类操作建议开启。 */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** 轻量受控确认弹窗，替代浏览器原生 confirm()，与墨色工坊风格统一。 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-md animate-fade-in"
        onClick={onCancel}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="corner-frame animate-fade-in-up relative w-full max-w-sm overflow-hidden rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        {/* 顶部色条：危险操作红色，普通翡翠 */}
        <div
          className={
            "absolute inset-x-0 top-0 h-[3px] " +
            (destructive ? "bg-destructive" : "bg-primary")
          }
        />
        <h2
          id="confirm-dialog-title"
          className="font-display text-lg font-semibold tracking-tight"
        >
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            {cancelText}
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            size="sm"
            onClick={onConfirm}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
}
