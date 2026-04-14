"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { getSteamAlerts, swrKeys } from "@/lib/api";
import { bookmakerLabel, formatSport } from "@/lib/utils";
import type { SteamAlert } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

export default function MarketIntelPage() {
  const [hoursBack, setHoursBack] = useState(6);

  const { data: steamAlerts, isLoading } = useSWR(
    swrKeys.steam(hoursBack),
    () => getSteamAlerts(hoursBack),
    { refreshInterval: 30_000 }
  );

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">Market Intelligence</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Steam moves · Sharp vs soft discrepancies · Line movement
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-2xs text-text-muted uppercase tracking-wide">Window</label>
            <select
              value={hoursBack}
              onChange={(e) => setHoursBack(Number(e.target.value))}
              className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
            >
              <option value={1}>1h</option>
              <option value={3}>3h</option>
              <option value={6}>6h</option>
              <option value={12}>12h</option>
              <option value={24}>24h</option>
            </select>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {/* Steam moves */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
              ⚡ Steam Moves
              {steamAlerts && (
                <span className="badge bg-steam/10 text-steam border-steam/30 text-2xs">
                  {steamAlerts.length}
                </span>
              )}
            </h2>
          </div>

          {isLoading ? (
            <div className="card p-8 text-center text-text-muted text-sm">Loading…</div>
          ) : !steamAlerts?.length ? (
            <div className="card p-8 text-center text-text-muted text-sm">
              No steam moves detected in the last {hoursBack}h.
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="table-head">Prop</th>
                    <th className="table-head">Direction</th>
                    <th className="table-head text-right">Line Δ</th>
                    <th className="table-head text-right">Velocity</th>
                    <th className="table-head">Books</th>
                    <th className="table-head">Detected</th>
                  </tr>
                </thead>
                <tbody>
                  {steamAlerts.map((alert) => (
                    <SteamRow key={alert.id} alert={alert} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Information cards */}
        <section className="grid grid-cols-2 gap-4">
          <InfoCard
            title="Sharp vs Soft — How it works"
            body={`Pinnacle is treated as the sharp reference price. When a soft book (DraftKings, FanDuel, etc.) deviates significantly from Pinnacle's implied probability, it signals a potential mispricing. PropEdge automatically flags these discrepancies and calculates edge.`}
          />
          <InfoCard
            title="Steam Move Detection"
            body={`A steam move is detected when ≥ 2 books move the same line by ≥ 0.5 pts within 5 minutes, suggesting coordinated sharp action. Velocity (pts/min) indicates how fast the market is moving. High velocity = strong signal.`}
          />
        </section>
      </div>
    </div>
  );
}

function SteamRow({ alert }: { alert: SteamAlert }) {
  const delta = alert.line_after - alert.line_before;

  return (
    <tr className="border-b border-border/50 hover:bg-surface-overlay transition-colors">
      <td className="table-cell">
        <Link href={`/props/${alert.id}`} className="text-accent hover:underline text-xs">
          View Prop #{alert.id}
        </Link>
      </td>
      <td className="table-cell">
        <span
          className={
            alert.direction === "over"
              ? "badge bg-ev-positive-muted text-ev-positive border-ev-positive/30"
              : "badge bg-ev-negative-muted text-ev-negative border-ev-negative/30"
          }
        >
          {alert.direction.toUpperCase()}
        </span>
      </td>
      <td className="table-cell text-right font-mono">
        <span className={delta > 0 ? "text-ev-positive" : "text-ev-negative"}>
          {delta > 0 ? "+" : ""}
          {delta.toFixed(1)} pts
        </span>
      </td>
      <td className="table-cell text-right font-mono text-text-secondary">
        {alert.velocity.toFixed(2)}/min
      </td>
      <td className="table-cell">
        <div className="flex items-center gap-1 flex-wrap">
          {alert.books_moved.map((b) => (
            <span key={b} className="badge text-2xs bg-surface-overlay text-text-muted border-border">
              {bookmakerLabel(b)}
            </span>
          ))}
        </div>
      </td>
      <td className="table-cell text-text-muted text-xs">
        {formatDistanceToNow(new Date(alert.detected_at), { addSuffix: true })}
      </td>
    </tr>
  );
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="card p-4">
      <h3 className="text-xs font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-xs text-text-secondary leading-relaxed">{body}</p>
    </div>
  );
}
