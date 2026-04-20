"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { getLineShop, swrKeys } from "@/lib/api";
import { bookmakerLabel, cn, formatAmerican, formatOdds, formatPct, formatSport, formatStatType, tierBg } from "@/lib/utils";
import { ConfidenceMeter } from "@/components/shared/ConfidenceMeter";
import type { PropSummary, Sport } from "@/lib/types";

const SPORTS: { value: Sport; label: string }[] = [
  { value: "basketball_nba", label: "NBA" },
  { value: "americanfootball_nfl", label: "NFL" },
  { value: "baseball_mlb", label: "MLB" },
  { value: "icehockey_nhl", label: "NHL" },
];

export default function LineShopPage() {
  const router = useRouter();
  const [sport, setSport] = useState<Sport | undefined>();
  const [minDispersion, setMinDispersion] = useState(0.25);
  const [minSoftBooks, setMinSoftBooks] = useState(1);

  const params = { sport, min_dispersion: minDispersion, min_soft_books: minSoftBooks, limit: 50 };

  const { data: props, isLoading } = useSWR(
    swrKeys.lineShop(params),
    () => getLineShop(params),
    { refreshInterval: 30_000 },
  );

  const totalSoftOps = props?.reduce((s, p) => s + (p.soft_book_count ?? 0), 0) ?? 0;

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">Line Shopping</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Props where books disagree · Find the best available number
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-text-muted">
            <span className="badge bg-surface-overlay border-border text-text-secondary">
              {props?.length ?? 0} props
            </span>
            <span className="badge bg-steam/10 text-steam border-steam/30">
              {totalSoftOps} soft lines
            </span>
          </div>
        </div>
      </header>

      {/* Explainer */}
      <div className="bg-accent/5 border-b border-accent/20 px-6 py-3">
        <p className="text-xs text-text-secondary leading-relaxed max-w-3xl">
          <span className="font-medium text-text-primary">How line shopping works:</span> A "soft" book is one whose implied probability sits ≥ 2.5pp below Pinnacle's no-vig line — they haven't adjusted to sharp action yet.
          High line dispersion (std dev of lines across books) means there's a real shopping opportunity. Act on the best-available number before it closes.
        </p>
      </div>

      {/* Filters */}
      <div className="border-b border-border px-6 py-3 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1">
          <button
            className={cn("px-2.5 py-1 rounded text-xs border transition-all", !sport ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary hover:text-text-primary")}
            onClick={() => setSport(undefined)}
          >All</button>
          {SPORTS.map(s => (
            <button
              key={s.value}
              className={cn("px-2.5 py-1 rounded text-xs border transition-all", sport === s.value ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary hover:text-text-primary")}
              onClick={() => setSport(sport === s.value ? undefined : s.value)}
            >{s.label}</button>
          ))}
        </div>
        <div className="w-px h-4 bg-border" />
        <div className="flex items-center gap-2">
          <label className="text-2xs text-text-muted uppercase tracking-wide">Min Dispersion</label>
          <select
            className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
            value={minDispersion}
            onChange={e => setMinDispersion(parseFloat(e.target.value))}
          >
            <option value={0}>Any</option>
            <option value={0.25}>0.25+</option>
            <option value={0.5}>0.5+</option>
            <option value={1.0}>1.0+</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-2xs text-text-muted uppercase tracking-wide">Min Soft Books</label>
          <select
            className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
            value={minSoftBooks}
            onChange={e => setMinSoftBooks(parseInt(e.target.value))}
          >
            <option value={1}>1+</option>
            <option value={2}>2+</option>
            <option value={3}>3+</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-[#0f1117]">
            <tr className="border-b border-border">
              <th className="table-head">Player</th>
              <th className="table-head">Prop</th>
              <th className="table-head text-right">Sharp Line</th>
              <th className="table-head text-right">Consensus</th>
              <th className="table-head">Best OVER</th>
              <th className="table-head">Best UNDER</th>
              <th className="table-head text-right">Dispersion</th>
              <th className="table-head text-right">Soft Books</th>
              <th className="table-head">EV</th>
              <th className="table-head">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
              : !props?.length
              ? (
                <tr>
                  <td colSpan={10} className="py-20 text-center text-text-muted text-sm">
                    No props found with current filters.
                    <p className="mt-1 text-2xs">Try reducing dispersion threshold or wait for next odds collection.</p>
                  </td>
                </tr>
              )
              : props.map(prop => (
                <LineShopRow key={prop.id} prop={prop} onClick={() => router.push(`/props/${prop.id}`)} />
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LineShopRow({ prop, onClick }: { prop: PropSummary; onClick: () => void }) {
  const softCount = prop.soft_book_count ?? 0;

  return (
    <tr
      onClick={onClick}
      className="border-b border-border/50 hover:bg-surface-overlay cursor-pointer transition-colors group"
    >
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-text-primary group-hover:text-accent transition-colors">
            {prop.player_name}
          </span>
          <span className="text-2xs text-text-muted">{formatSport(prop.sport)}</span>
        </div>
      </td>
      <td className="table-cell text-text-secondary">{formatStatType(prop.stat_type)}</td>
      <td className="table-cell text-right font-mono font-medium">{prop.line}</td>
      <td className="table-cell text-right font-mono text-text-secondary">
        {prop.consensus_line != null ? prop.consensus_line.toFixed(1) : "—"}
      </td>
      <td className="table-cell">
        {prop.best_over_book ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-medium text-ev-positive">{bookmakerLabel(prop.best_over_book)}</span>
            <span className="text-2xs font-mono text-text-muted">
              {prop.best_over_odds ? formatAmerican(prop.best_over_odds) : "—"}
            </span>
          </div>
        ) : <span className="text-text-muted">—</span>}
      </td>
      <td className="table-cell">
        {prop.best_under_book ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-medium text-ev-negative">{bookmakerLabel(prop.best_under_book)}</span>
            <span className="text-2xs font-mono text-text-muted">
              {prop.best_under_odds ? formatAmerican(prop.best_under_odds) : "—"}
            </span>
          </div>
        ) : <span className="text-text-muted">—</span>}
      </td>
      <td className="table-cell text-right font-mono">
        {prop.line_dispersion != null ? (
          <span className={prop.line_dispersion >= 0.5 ? "text-ev-neutral font-semibold" : "text-text-secondary"}>
            ±{prop.line_dispersion.toFixed(2)}
          </span>
        ) : "—"}
      </td>
      <td className="table-cell text-right">
        <SoftBooksIndicator count={softCount} />
      </td>
      <td className="table-cell">
        {prop.ev != null && prop.tier ? (
          <span className={cn("badge text-2xs", tierBg(prop.tier))}>
            {prop.tier === "elite" && "🔥 "}
            {prop.tier === "high" && "⚡ "}
            EV {(prop.ev * 100).toFixed(1)}%
          </span>
        ) : <span className="text-text-muted text-xs">—</span>}
      </td>
      <td className="table-cell min-w-[100px]">
        <ConfidenceMeter score={prop.confidence ?? 0} size="sm" />
      </td>
    </tr>
  );
}

function SoftBooksIndicator({ count }: { count: number }) {
  if (count === 0) return <span className="text-text-muted text-xs">—</span>;
  return (
    <span className={cn(
      "badge text-2xs",
      count >= 3 ? "bg-ev-neutral/20 text-ev-neutral border-ev-neutral/30" :
      count >= 2 ? "bg-steam/10 text-steam border-steam/30" :
      "bg-surface-overlay text-text-secondary border-border"
    )}>
      {count} soft
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-border/50">
      {Array.from({ length: 10 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div className="h-3.5 bg-surface-overlay rounded animate-pulse" style={{ width: `${40 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  );
}
