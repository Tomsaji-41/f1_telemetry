import * as React from "react";
import { cn } from "@/lib/cn";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "f1" | "success" | "warning" | "outline" | "cyan";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps): React.JSX.Element {
  const variantStyles = {
    default: "bg-slate-800 text-slate-200 border-slate-700",
    f1: "bg-gradient-to-r from-red-600 to-rose-800 text-white font-bold tracking-wider uppercase border-red-500/30",
    cyan: "bg-emerald-950/80 text-teal-300 border-teal-500/30 font-semibold",
    success: "bg-emerald-900/60 text-emerald-300 border-emerald-500/30",
    warning: "bg-amber-900/60 text-amber-300 border-amber-500/30",
    outline: "border-slate-700 text-slate-400 bg-transparent",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors select-none",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}
