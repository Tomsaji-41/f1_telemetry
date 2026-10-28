import * as React from "react";
import { cn } from "@/lib/cn";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element {
  return (
    <div
      role="status"
      aria-label="Loading content"
      className={cn("animate-pulse rounded-md bg-slate-800/80", className)}
      {...props}
    />
  );
}
