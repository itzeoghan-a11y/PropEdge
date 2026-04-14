"use client";

import { cn, formatEdge, tierBg } from "@/lib/utils";
import type { Tier } from "@/lib/types";

interface EVBadgeProps {
  ev: number;
  tier: Tier | null;
  className?: string;
}

export function EVBadge({ ev, tier, className }: EVBadgeProps) {
  return (
    <span className={cn("badge", tierBg(tier), className)}>
      {tier === "elite" && "🔥 "}
      {tier === "high" && "⚡ "}
      EV {(ev * 100).toFixed(2)}%
    </span>
  );
}

interface EdgeBadgeProps {
  edge: number;
  className?: string;
}

export function EdgeBadge({ edge, className }: EdgeBadgeProps) {
  const color =
    edge >= 0.10 ? "text-elite border-elite/30 bg-elite/10" :
    edge >= 0.05 ? "text-ev-positive border-ev-positive/30 bg-ev-positive-muted" :
    "text-ev-neutral border-ev-neutral/30 bg-ev-neutral/10";

  return (
    <span className={cn("badge", color, className)}>
      {formatEdge(edge)}
    </span>
  );
}
