"use client";

import { useRouter } from "next/navigation";
import {
  bookmakerLabel,
  cn,
  formatAmerican,
  formatOdds,
  formatPct,
  formatSport,
  formatStatType,
  tierBg,
} from "@/lib/utils";
import { ConfidenceMeter } from "@/components/shared/ConfidenceMeter";
import { EVBadge } from "@/components/shared/EVBadge";
import type { PropSummary } from "@/lib/types";

interface PropsTableProps {
  props: PropSummary[];
  loading: boolean;
  error?: Error | null;
}

export function PropsTable({ props, loading, error }: PropsTableProps) {
  const router = useRouter();

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-text-secondary text-sm">
        Failed to load props. Check your connection.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-[#0f1117] sticky top-0 z-10">
            <th className="table-head w-8">#</th>
            <th className="table-head">Player</th>
            <th className="table-head">Prop</th>
            <th className="table-head text-right">Line</th>
            <th className="table-head">Dir</th>
            <th className="table-head">Best Book</th>
            <th className="table-head text-right">Odds</th>
            <th className="table-head text-right">Model%</th>
            <th className="table-head text-right">Edge</th>
            <th className="table-head text-right">EV</th>
            <th className="table-head">Confidence</th>
            <th className="table-head">Line Shop</th>
            <th className="table-head">Status</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 8 }).map((_, i) => (
              <SkeletonRow key={i} index={i} />
            ))
          ) : props.length === 0 ? (
            <tr>
              <td colSpan={13} className="py-16 text-center text-text-muted text-sm">
                No props match current filters.
              </td>
            </tr>
          ) : (
            props.map((prop, idx) => (
              <PropRow
                key={`${prop.id}-${prop.best_direction}`}
                prop={prop}
                index={idx + 1}
                onClick={() => router.push(`/props/${prop.id}`)}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function PropRow({
  prop,
  index,
  onClick,
}: {
  prop: PropSummary;
  index: number;
  onClick: () => void;
}) {
  const ev = prop.ev ?? 0;
  const edge = prop.edge ?? 0;

  return (
    <tr
      onClick={onClick}
      className="border-b border-border/50 hover:bg-surface-overlay cursor-pointer transition-colors group"
    >
      {/* Index */}
      <td className="table-cell text-text-muted font-mono text-xs">{index}</td>

      {/* Player */}
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-text-primary group-hover:text-accent transition-colors">
            {prop.player_name}
          </span>
          <span className="text-2xs text-text-muted">{formatSport(prop.sport)}</span>
        </div>
      </td>

      {/* Prop type */}
      <td className="table-cell">
        <span className="text-text-secondary">{formatStatType(prop.stat_type)}</span>
      </td>

      {/* Line */}
      <td className="table-cell text-right font-mono font-medium">{prop.line}</td>

      {/* Direction */}
      <td className="table-cell">
        <span
          className={cn(
            "badge",
            prop.best_direction === "over"
              ? "bg-ev-positive-muted text-ev-positive border-ev-positive/30"
              : "bg-ev-negative-muted text-ev-negative border-ev-negative/30",
          )}
        >
          {prop.best_direction?.toUpperCase() ?? "—"}
        </span>
      </td>

      {/* Book */}
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="text-text-secondary text-xs">{bookmakerLabel(prop.best_bookmaker ?? "")}</span>
          {prop.best_bookmaker && (
            prop.best_direction === "over"
              ? prop.best_bookmaker === prop.best_over_book
              : prop.best_bookmaker === prop.best_under_book
          ) && (
            <span className="text-2xs text-accent">Best avail.</span>
          )}
        </div>
      </td>

      {/* Odds */}
      <td className="table-cell text-right font-mono text-text-secondary">
        {prop.best_book_odds ? formatAmerican(prop.best_book_odds) : "—"}
      </td>

      {/* Model % */}
      <td className="table-cell text-right font-mono">
        <span className="text-text-primary">
          {prop.model_prob ? formatPct(prop.model_prob) : "—"}
        </span>
      </td>

      {/* Edge */}
      <td className="table-cell text-right font-mono">
        <span className={cn("font-semibold", edge >= 0.10 ? "text-elite" : edge >= 0.05 ? "text-ev-positive" : "text-ev-neutral")}>
          {edge ? `+${(edge * 100).toFixed(2)}%` : "—"}
        </span>
      </td>

      {/* EV */}
      <td className="table-cell text-right">
        <EVBadge ev={ev} tier={prop.tier} />
      </td>

      {/* Confidence */}
      <td className="table-cell min-w-[100px]">
        <ConfidenceMeter score={prop.confidence ?? 0} size="sm" />
      </td>

      {/* Line shopping summary */}
      <td className="table-cell">
        {prop.line_dispersion != null && prop.line_dispersion > 0 ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-2xs font-mono text-text-muted">±{prop.line_dispersion.toFixed(2)}</span>
            {(prop.soft_book_count ?? 0) > 0 && (
              <span className="text-2xs text-ev-neutral">{prop.soft_book_count} soft</span>
            )}
          </div>
        ) : (
          <span className="text-text-muted text-xs">—</span>
        )}
      </td>

      {/* Status badges */}
      <td className="table-cell">
        <div className="flex items-center gap-1 flex-wrap">
          {prop.has_steam && (
            <span className="badge bg-steam/10 text-steam border-steam/30 text-2xs">
              ⚡ Steam
            </span>
          )}
          {prop.steam_boosted && !prop.has_steam && (
            <span className="badge bg-steam/5 text-steam/70 border-steam/20 text-2xs">⚡</span>
          )}
          {prop.tier && (
            <span className={cn("badge text-2xs", tierBg(prop.tier))}>
              {prop.tier === "elite" ? "🔥" : prop.tier === "high" ? "⚡" : ""} {prop.tier}
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}

function SkeletonRow({ index }: { index: number }) {
  return (
    <tr className="border-b border-border/50">
      {Array.from({ length: 13 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div
            className="h-3.5 bg-surface-overlay rounded animate-pulse"
            style={{ width: `${50 + Math.random() * 50}%`, opacity: 1 - index * 0.08 }}
          />
        </td>
      ))}
    </tr>
  );
}
