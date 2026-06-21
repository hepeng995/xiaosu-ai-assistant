import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-lg border border-input bg-background/50 px-3 py-1 text-sm shadow-sm backdrop-blur-sm transition-all duration-200",
        "placeholder:text-muted-foreground/60",
        "focus-visible:outline-none focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:bg-background",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
