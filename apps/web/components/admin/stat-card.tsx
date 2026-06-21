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

/** 概览统计卡片：编号角标 + 着色图标 + 等宽大数字，悬停翡翠光晕。 */
export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = "default",
}: StatCardProps) {
  return (
    <Card className="glow-ring corner-frame group relative flex items-center gap-4 overflow-hidden p-5">
      <div
        className={cn(
          "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
          TONE_CLASS[tone],
        )}
      >
        <Icon className="h-5 w-5" strokeWidth={1.7} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
          {label}
        </div>
        <div className="mt-1 font-display text-[26px] font-semibold leading-none tracking-tight tabular-nums">
          {value}
        </div>
        {hint && (
          <div className="mt-1.5 truncate font-mono text-[11px] text-muted-foreground/60">
            {hint}
          </div>
        )}
      </div>
    </Card>
  );
}
