import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
}

/** 统一的空状态：虚线翡翠圈图标 + 衬线标题 + 可选说明。 */
export function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="relative flex h-14 w-14 items-center justify-center">
        <div className="absolute inset-0 rounded-full border border-dashed border-primary/30" />
        <div className="absolute inset-2 rounded-full bg-primary/5" />
        <Icon className="relative h-6 w-6 text-primary/70" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <p className="font-display text-base font-medium tracking-tight text-foreground">
          {title}
        </p>
        {description && (
          <p className="mx-auto max-w-sm text-xs text-muted-foreground">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
