"use client";

import { cn } from "@/lib/utils";

interface ConfidenceMeterProps {
  score: number;  // 0–100
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function ConfidenceMeter({ score, showLabel = true, size = "md" }: ConfidenceMeterProps) {
  const color =
    score >= 80 ? "bg-ev-positive" :
    score >= 60 ? "bg-ev-neutral" :
    "bg-text-muted";

  const textColor =
    score >= 80 ? "text-ev-positive" :
    score >= 60 ? "text-ev-neutral" :
    "text-text-muted";

  return (
    <div className={cn("flex items-center gap-2", size === "sm" && "gap-1.5")}>
      <div className={cn("relative flex-1 bg-border rounded-full overflow-hidden", size === "sm" ? "h-1" : "h-1.5")}>
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      {showLabel && (
        <span className={cn("font-mono text-xs font-medium tabular-nums", textColor)}>
          {score.toFixed(0)}
        </span>
      )}
    </div>
  );
}
