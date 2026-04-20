"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { getSteamAlerts, getLineShop, swrKeys } from "@/lib/api";
import { bookmakerLabel, cn, formatAmerican, formatPct, formatSport, formatStatType } from "@/lib/utils";
import { EVBadge } from "@/components/shared/EVBadge";
import type { SteamAlert, PropSummary } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

export default function MarketIntelPage() {
  const [hoursBack, setHoursBack] = useState(6);
  const [sport, setSport] = useState<string>("");

  const { data: steamAlerts, isLoading: steamLoading } = useSWR(
    swrKeys.steam(hoursBack),
    () => getSteamAlerts(hoursBack),
    { refreshInterval: 30_000 }
  );

  const lineShopParams = { sport: sport || undefined, min_dispersion: 0.2, limit: 20 };
  const { data: lineShopProps, isLoading: lineLoading } = useSWR(
    swrKeys.lineShop(lineShopParams),
    () => getLineShop(lineShopParams),
    { refreshInterval: 60_000 }
  );

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">Market Intelligence</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Steam moves · Sharp vs soft discrepancies · Line shopping
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <label className="text-2xs text-text-muted uppercase tracking-wide">Sport</label>
              <select
                value={sport}
                onChange={(e) => setSport(e.target.value)}
                className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
              >
                <option value="">All</option>
                <option value="basketball_nba">NBA</option>
                <option value="americanfootball_nfl">NFL</option>
                <option value="baseball_mlb">MLB</option>
                <option value="icehockey_nhl">NHL</option>
              </select>
            </div>
            <div className="flex items-center gap-1.5">
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

          {steamLoading ? (
            <div className="card p-8 text-center text-text-muted text-sm animate-pulse">Loading…</div>
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
                    <th className="table-head">Books Moved</th>
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

        {/* Line Shopping — Best Discrepancies */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-text-primary flex items-center gap-2">
              🔍 Best Line Shopping Opportunities
              {lineShopProps && (
                <span className="badge bg-accent/10 text-accent border-accent/30 text-2xs">
                  {lineShopProps.length}
                </span>
              )}
            </h2>
            <Link href="/line-shop" className="text-2xs text-accent hover:underline">
              Full line shop →
            </Link>
          </div>

          {lineLoading ? (
            <div className="card p-8 text-center text-text-muted text-sm animate-pulse">Loading…</div>
          ) : !lineShopProps?.length ? (
            <div className="card p-8 text-center text-text-muted text-sm">
              No significant line discrepancies detected.
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="table-head">Player</th>
                    <th className="table-head">Prop</th>
                    <th className="table-head text-right">Sharp Line</th>
                    <th className="table-head">Best Over</th>
                    <th className="table-head">Best Under</th>
                    <th className="table-head text-right">Dispersion</th>
                    <th className="table-head text-right">EV</th>
                  </tr>
                </thead>
                <tbody>
                  {lineShopProps.map((prop) => (
                    <LineShopRow key={prop.id} prop={prop} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* How it works */}
        <section className="grid grid-cols-2 gap-4">
          <InfoCard
            title="Steam Move Detection"
            body="A steam move fires when ≥ 2 books move the same line ≥ 0.5 pts within 5 minutes — a signal of coordinated sharp action. High velocity (pts/min) indicates faster market movement and a stronger signal. Steam moves get a confidence boost of up to +15 pts."
          />
          <InfoCard
            title="Line Shopping — Sharp vs Soft"
            body="Pinnacle is the reference sharp price. Soft books (DK, FD, MGM, Caesars) that deviate ≥ 2.5 pp from Pinnacle's no-vig implied probability are flagged. Line dispersion (std-dev across books) quantifies how spread the market is — wider spreads = more arbitrage opportunity."
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
        <Link href={`/props/${alert.id}`} className="text-accent hover:underline text-xs font-mono">
          #{alert.id}
        </Link>
      </td>
      <td className="table-cell">
        <span
          className={cn(
            "badge",
            alert.direction === "over"
              ? "bg-ev-positive-muted text-ev-positive border-ev-positive/30"
              : "bg-ev-negative-muted text-ev-negative border-ev-negative/30",
          )}
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

function LineShopRow({ prop }: { prop: PropSummary }) {
  return (
    <tr
      className="border-b border-border/50 hover:bg-surface-overlay transition-colors cursor-pointer"
      onClick={() => window.location.assign(`/props/${prop.id}`)}
    >
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-text-primary text-xs">{prop.player_name}</span>
          <span className="text-2xs text-text-muted">{formatSport(prop.sport)}</span>
        </div>
      </td>
      <td className="table-cell text-text-secondary text-xs">{formatStatType(prop.stat_type)}</td>
      <td className="table-cell text-right font-mono text-xs">
        {prop.consensus_line != null ? prop.consensus_line.toFixed(1) : prop.line.toFixed(1)}
      </td>
      <td className="table-cell">
        {prop.best_over_book ? (
          <div className="flex flex-col gap-0">
            <span className="text-xs text-ev-positive font-medium">{bookmakerLabel(prop.best_over_book)}</span>
            {prop.best_over_odds && (
              <span className="text-2xs font-mono text-text-muted">{formatAmerican(prop.best_over_odds)}</span>
            )}
          </div>
        ) : (
          <span className="text-text-muted text-xs">—</span>
        )}
      </td>
      <td className="table-cell">
        {prop.best_under_book ? (
          <div className="flex flex-col gap-0">
            <span className="text-xs text-ev-negative font-medium">{bookmakerLabel(prop.best_under_book)}</span>
            {prop.best_under_odds && (
              <span className="text-2xs font-mono text-text-muted">{formatAmerican(prop.best_under_odds)}</span>
            )}
          </div>
        ) : (
          <span className="text-text-muted text-xs">—</span>
        )}
      </td>
      <td className="table-cell text-right">
        {prop.line_dispersion != null ? (
          <div className="flex flex-col items-end gap-0">
            <span className="font-mono text-xs text-text-primary">±{prop.line_dispersion.toFixed(2)}</span>
            {(prop.soft_book_count ?? 0) > 0 && (
              <span className="text-2xs text-ev-neutral">{prop.soft_book_count} soft</span>
            )}
          </div>
        ) : (
          <span className="text-text-muted text-xs">—</span>
        )}
      </td>
      <td className="table-cell text-right">
        {prop.ev != null ? <EVBadge ev={prop.ev} tier={prop.tier} /> : <span className="text-text-muted text-xs">—</span>}
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
