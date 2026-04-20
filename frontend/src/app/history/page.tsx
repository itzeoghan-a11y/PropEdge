"use client";

import { useState } from "react";
import useSWR from "swr";
import { getBetHistory, swrKeys } from "@/lib/api";
import { bookmakerLabel, cn, formatAmerican, formatPct, formatSport, formatStatType, tierBg } from "@/lib/utils";
import type { BetRecord, Sport, Tier } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

const SPORTS: { value: Sport; label: string }[] = [
  { value: "basketball_nba", label: "NBA" },
  { value: "americanfootball_nfl", label: "NFL" },
  { value: "baseball_mlb", label: "MLB" },
  { value: "icehockey_nhl", label: "NHL" },
];

const TIERS: { value: Tier; label: string }[] = [
  { value: "elite", label: "Elite" },
  { value: "high", label: "High" },
  { value: "standard", label: "Standard" },
];

function dateStr(d: Date) {
  return d.toISOString().split("T")[0];
}

export default function HistoryPage() {
  const [sport, setSport] = useState<Sport | undefined>();
  const [tier, setTier] = useState<Tier | undefined>();
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return dateStr(d);
  });
  const [dateTo] = useState(() => dateStr(new Date()));

  const params = { sport, tier, date_from: dateFrom, date_to: dateTo, resolved_only: true, limit: 200 };

  const { data, isLoading } = useSWR(
    swrKeys.history(params),
    () => getBetHistory(params),
    { refreshInterval: 60_000 },
  );

  const summary = data?.summary;
  const bets = data?.bets ?? [];

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">Bet History</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Every flagged +EV opportunity with resolved results and P&L
            </p>
          </div>
          {summary && (
            <div className="flex items-center gap-1 text-2xs text-text-muted">
              <span>{summary.resolved} resolved</span>
              <span>·</span>
              <span className={summary.roi != null && summary.roi > 0 ? "text-ev-positive font-medium" : "text-ev-negative font-medium"}>
                ROI {summary.roi != null ? `${(summary.roi * 100).toFixed(1)}%` : "—"}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Summary cards */}
      {summary && (
        <div className="border-b border-border px-6 py-4 grid grid-cols-6 gap-4">
          <SummaryCard label="Total Flagged" value={String(summary.total_flagged)} />
          <SummaryCard label="Resolved" value={String(summary.resolved)} />
          <SummaryCard label="Wins" value={String(summary.wins)} color="text-ev-positive" />
          <SummaryCard label="Losses" value={String(summary.losses)} color="text-ev-negative" />
          <SummaryCard
            label="Win Rate"
            value={summary.win_rate != null ? formatPct(summary.win_rate) : "—"}
            color={summary.win_rate != null && summary.win_rate >= 0.52 ? "text-ev-positive" : "text-text-primary"}
          />
          <SummaryCard
            label="ROI (flat $1)"
            value={summary.roi != null ? `${summary.roi > 0 ? "+" : ""}${(summary.roi * 100).toFixed(2)}%` : "—"}
            color={summary.roi != null && summary.roi > 0 ? "text-ev-positive" : "text-ev-negative"}
          />
        </div>
      )}

      {/* Filters */}
      <div className="border-b border-border px-6 py-3 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1">
          <button
            className={cn("px-2.5 py-1 rounded text-xs border transition-all", !sport ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary")}
            onClick={() => setSport(undefined)}
          >All Sports</button>
          {SPORTS.map(s => (
            <button
              key={s.value}
              className={cn("px-2.5 py-1 rounded text-xs border transition-all", sport === s.value ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary")}
              onClick={() => setSport(sport === s.value ? undefined : s.value)}
            >{s.label}</button>
          ))}
        </div>
        <div className="w-px h-4 bg-border" />
        <div className="flex items-center gap-1">
          {TIERS.map(t => (
            <button
              key={t.value}
              className={cn("px-2.5 py-1 rounded text-xs border transition-all", tier === t.value ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary")}
              onClick={() => setTier(tier === t.value ? undefined : t.value)}
            >{t.label}</button>
          ))}
        </div>
        <div className="w-px h-4 bg-border" />
        <div className="flex items-center gap-2">
          <label className="text-2xs text-text-muted">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-[#0f1117]">
            <tr className="border-b border-border">
              <th className="table-head">Player</th>
              <th className="table-head">Prop</th>
              <th className="table-head">Dir</th>
              <th className="table-head">Book</th>
              <th className="table-head text-right">Odds</th>
              <th className="table-head text-right">Edge</th>
              <th className="table-head text-right">EV</th>
              <th className="table-head">Tier</th>
              <th className="table-head text-right">Result</th>
              <th className="table-head text-right">P&L</th>
              <th className="table-head text-right">CLV</th>
              <th className="table-head">Flags</th>
              <th className="table-head">Date</th>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 10 }).map((_, i) => <SkeletonRow key={i} />)
              : !bets.length
              ? (
                <tr>
                  <td colSpan={13} className="py-20 text-center text-text-muted text-sm">
                    No resolved bets found for this period.
                    <p className="mt-1 text-2xs">Bets appear here once game results are entered.</p>
                  </td>
                </tr>
              )
              : bets.map(bet => <BetRow key={bet.id} bet={bet} />)
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BetRow({ bet }: { bet: BetRecord }) {
  const won = bet.won;
  const pnl = bet.pnl;
  const clv = bet.clv;

  return (
    <tr className="border-b border-border/50 hover:bg-surface-overlay transition-colors">
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-text-primary">{bet.player_name}</span>
          <span className="text-2xs text-text-muted">{formatSport(bet.sport)}</span>
        </div>
      </td>
      <td className="table-cell">
        <span className="text-text-secondary">{formatStatType(bet.stat_type)}</span>
        <span className="text-text-muted font-mono ml-1">{bet.line}</span>
      </td>
      <td className="table-cell">
        <span className={cn("badge", bet.direction === "over" ? "bg-ev-positive-muted text-ev-positive border-ev-positive/30" : "bg-ev-negative-muted text-ev-negative border-ev-negative/30")}>
          {bet.direction.toUpperCase()}
        </span>
      </td>
      <td className="table-cell text-text-secondary text-xs">
        <div className="flex flex-col gap-0.5">
          {bookmakerLabel(bet.bookmaker)}
          {bet.is_best_available_line && (
            <span className="text-2xs text-accent">Best Line</span>
          )}
        </div>
      </td>
      <td className="table-cell text-right font-mono text-text-secondary">
        {formatAmerican(bet.book_odds)}
      </td>
      <td className="table-cell text-right font-mono font-semibold text-ev-positive">
        +{(bet.edge * 100).toFixed(1)}%
      </td>
      <td className="table-cell text-right font-mono text-text-secondary">
        {(bet.ev * 100).toFixed(1)}%
      </td>
      <td className="table-cell">
        <span className={cn("badge text-2xs", tierBg(bet.tier))}>{bet.tier}</span>
      </td>
      <td className="table-cell text-right">
        {!bet.resolved ? (
          <span className="text-text-muted text-xs">Pending</span>
        ) : won === true ? (
          <span className="font-medium text-ev-positive">WIN</span>
        ) : (
          <span className="font-medium text-ev-negative">LOSS</span>
        )}
      </td>
      <td className="table-cell text-right font-mono">
        {pnl != null ? (
          <span className={pnl >= 0 ? "text-ev-positive font-medium" : "text-ev-negative font-medium"}>
            {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}u
          </span>
        ) : <span className="text-text-muted">—</span>}
      </td>
      <td className="table-cell text-right font-mono">
        {clv != null ? (
          <span className={clv >= 0 ? "text-ev-positive" : "text-ev-negative"}>
            {clv >= 0 ? "+" : ""}{(clv * 100).toFixed(1)}%
          </span>
        ) : <span className="text-text-muted text-xs">—</span>}
      </td>
      <td className="table-cell">
        <div className="flex items-center gap-1">
          {bet.steam_boosted && (
            <span className="badge text-2xs bg-steam/10 text-steam border-steam/30">⚡</span>
          )}
        </div>
      </td>
      <td className="table-cell text-text-muted text-xs font-mono">{bet.game_date}</td>
    </tr>
  );
}

function SummaryCard({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return (
    <div className="card p-3 text-center">
      <p className="text-2xs text-text-muted uppercase tracking-wide">{label}</p>
      <p className={cn("font-mono font-semibold text-sm mt-1", color)}>{value}</p>
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-border/50">
      {Array.from({ length: 13 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div className="h-3.5 bg-surface-overlay rounded animate-pulse" style={{ width: `${40 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  );
}
