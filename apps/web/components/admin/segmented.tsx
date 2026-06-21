"use client";

interface SegmentedOption {
  value: string;
  label: string;
}

interface SegmentedProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
}

/** 分段筛选器：互斥选项，当前项翡翠高亮。文档/日志筛选复用。 */
export function Segmented({ options, value, onChange }: SegmentedProps) {
  return (
    <div className="flex w-full items-center gap-0.5 overflow-x-auto rounded-lg border border-border/70 bg-card/60 p-0.5 backdrop-blur-sm sm:inline-flex sm:w-auto">
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={
              "shrink-0 rounded-md px-3 py-1 text-xs font-medium transition-all duration-200 " +
              (active
                ? "bg-primary/12 text-primary shadow-sm"
                : "text-muted-foreground hover:bg-muted hover:text-foreground")
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
