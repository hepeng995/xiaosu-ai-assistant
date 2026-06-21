interface PageHeaderProps {
  title: string;
  description?: string;
  /** 标题左侧的小型 eyebrow 标签（如章节编号 / 分类）。 */
  eyebrow?: string;
  /** 右侧操作区（按钮、开关等）。 */
  children?: React.ReactNode;
}

/**
 * 统一的页面标题区：eyebrow 编号 + 衬线大标题 + 描述 + 右侧操作插槽。
 * 底部一条翡翠渐隐分隔线，强化 editorial 章节感。
 */
export function PageHeader({ title, description, eyebrow, children }: PageHeaderProps) {
  return (
    <div className="animate-fade-in-up relative space-y-3 pb-1">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1.5">
          {eyebrow && (
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.22em] text-primary/80">
              <span className="inline-block h-px w-6 bg-primary/50" />
              {eyebrow}
            </div>
          )}
          <h1 className="font-display text-[28px] font-semibold leading-tight tracking-tight md:text-3xl">
            {title}
          </h1>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {children && (
          <div className="flex items-center gap-2">{children}</div>
        )}
      </div>
      {/* 翡翠渐隐分隔线 */}
      <div className="h-px w-full bg-gradient-to-r from-border via-border/40 to-transparent" />
    </div>
  );
}
