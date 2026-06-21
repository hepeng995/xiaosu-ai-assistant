import { cn } from "@/lib/utils";

/** 加载占位骨架块，配合 animate-pulse 呈现加载态。 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

export { Skeleton };
