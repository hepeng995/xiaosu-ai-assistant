interface PageHeaderProps {
  title: string;
  description?: string;
  /** 右侧操作区（按钮、开关等）。 */
  children?: React.ReactNode;
}

/** 统一的页面标题区：左侧标题 + 描述，右侧操作插槽。 */
export function PageHeader({ title, description, children }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold">{title}</h1>
        {description && (
          <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
