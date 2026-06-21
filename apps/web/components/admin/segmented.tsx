"use client";

import { Button } from "@/components/ui/button";

interface SegmentedOption {
  value: string;
  label: string;
}

interface SegmentedProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
}

/** 分段筛选器：一组互斥选项按钮，当前项高亮。文档/日志筛选复用。 */
export function Segmented({ options, value, onChange }: SegmentedProps) {
  return (
    <div className="inline-flex rounded-md border border-border bg-card p-0.5">
      {options.map((opt) => (
        <Button
          key={opt.value}
          type="button"
          variant={value === opt.value ? "secondary" : "ghost"}
          size="sm"
          className="h-7"
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  );
}
