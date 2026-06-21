import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Tone = "default" | "success" | "warning" | "destructive";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  hint?: string;
  tone?: Tone;
}

const TONE_CLASS: Record<Tone, string> = {
  default: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  destructive: "bg-destructive/10 text-destructive",
};

/** 概览统计卡片：左侧着色图标 + 右侧数值与标签。 */
export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = "default",
}: StatCardProps) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div
        className={cn(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg",
          TONE_CLASS[tone],
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-tight">{value}</div>
        <div className="truncate text-xs text-muted-foreground">{label}</div>
        {hint && (
          <div className="truncate text-[11px] text-muted-foreground/70">
            {hint}
          </div>
        )}
      </div>
    </Card>
  );
}
