"use client";

import { use } from "react";
import useSWR from "swr";
import Link from "next/link";
import { getPropDetail, swrKeys } from "@/lib/api";
import { ConfidenceMeter } from "@/components/shared/ConfidenceMeter";
import { EVBadge, EdgeBadge } from "@/components/shared/EVBadge";
import {
  bookmakerLabel,
  cn,
  defRankLabel,
  formatAmerican,
  formatOdds,
  formatPct,
  formatSport,
  formatStatType,
  tierBg,
} from "@/lib/utils";
import type { EVOpportunity, LineShopping, OddsRow } from "@/lib/types";

export default function PropDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useSWR(swrKeys.propDetail(Number(id)), () =>
    getPropDetail(Number(id))
  );

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64 text-text-secondary text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-text-muted">
        <Link href="/" className="hover:text-text-secondary transition-colors">Dashboard</Link>
        <span>/</span>
        <Link href={`/players/${data.player_id}`} className="hover:text-text-secondary transition-colors">
          {data.player_name}
        </Link>
        <span>/</span>
        <span className="text-text-secondary">{formatStatType(data.stat_type)}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{data.player_name}</h1>
            <span className="badge bg-surface-overlay text-text-secondary border-border">
              {formatSport(data.sport)}
            </span>
            {data.steam_alerts.length > 0 && (
              <span className="badge bg-steam/10 text-steam border-steam/30">⚡ Steam Active</span>
            )}
          </div>
          <p className="text-text-secondary mt-1">
            {formatStatType(data.stat_type)} · Line {data.line} · vs {data.opponent_team} · {data.game_date}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {data.line_shopping?.line_dispersion != null && data.line_shopping.line_dispersion > 0 && (
            <div className="text-right">
              <p className="text-2xs text-text-muted uppercase tracking-wide">Line Dispersion</p>
              <p className="font-mono font-medium mt-0.5 text-ev-neutral">±{data.line_shopping.line_dispersion.toFixed(2)}</p>
            </div>
          )}
          <div className="text-right">
            <p className="text-2xs text-text-muted uppercase tracking-wide">Sample Size</p>
            <p className="font-mono font-medium mt-0.5">{data.sample_size} games</p>
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-3 gap-6">
        {/* Left: Opportunities + Model + Odds */}
        <div className="col-span-2 space-y-6">
          {/* EV Opportunities */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">EV Opportunities</h2>
              <span className="text-2xs text-text-muted">{data.ev_opportunities.length} found</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="table-head">Direction</th>
                    <th className="table-head">Book</th>
                    <th className="table-head text-right">Odds</th>
                    <th className="table-head text-right">Model%</th>
                    <th className="table-head text-right">Implied%</th>
                    <th className="table-head text-right">Edge</th>
                    <th className="table-head text-right">EV</th>
                    <th className="table-head">Tier</th>
                    <th className="table-head">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ev_opportunities.map((opp) => (
                    <EVRow key={opp.id} opp={opp} />
                  ))}
                  {data.ev_opportunities.length === 0 && (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-text-muted text-sm">
                        No EV opportunities currently meet thresholds.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Line Shopping Detail */}
          {data.line_shopping && data.line_shopping.book_details.length > 0 && (
            <LineShoppingPanel shopping={data.line_shopping} />
          )}

          {/* Model Breakdown */}
          {data.model_breakdown && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Model Breakdown</h2>
                <span className="text-2xs text-text-muted">
                  {data.model_breakdown.n_models} model(s) combined
                </span>
              </div>
              <div className="p-4 space-y-4">
                <ModelProbRow
                  label="Ensemble (Final)"
                  prob={data.model_breakdown.final_prob_over}
                  weight={1}
                  isPrimary
                />
                <div className="border-t border-border pt-4 space-y-3">
                  {data.model_breakdown.distribution_prob != null && (
                    <ModelProbRow label="Distribution Model" prob={data.model_breakdown.distribution_prob}
                      weight={data.model_breakdown.weights_used["distribution"] ?? 0} />
                  )}
                  {data.model_breakdown.bayesian_prob != null && (
                    <ModelProbRow label="Bayesian Model" prob={data.model_breakdown.bayesian_prob}
                      weight={data.model_breakdown.weights_used["bayesian"] ?? 0} />
                  )}
                  {data.model_breakdown.ml_prob != null && (
                    <ModelProbRow label="ML Model (XGBoost)" prob={data.model_breakdown.ml_prob}
                      weight={data.model_breakdown.weights_used["ml"] ?? 0} />
                  )}
                  {data.model_breakdown.sharp_prob != null && (
                    <ModelProbRow label="Sharp Line (Pinnacle)" prob={data.model_breakdown.sharp_prob}
                      weight={data.model_breakdown.weights_used["sharp"] ?? 0} />
                  )}
                </div>
                <div className="flex items-center gap-2 pt-2">
                  <span className="text-xs text-text-muted">Confidence:</span>
                  <div className="flex-1">
                    <ConfidenceMeter score={data.model_breakdown.confidence} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Context panel */}
        <div className="space-y-4">
          <WhyThisBet prop={data} />
          {data.steam_alerts.length > 0 && <SteamPanel alerts={data.steam_alerts} />}
        </div>
      </div>
    </div>
  );
}

function EVRow({ opp }: { opp: EVOpportunity }) {
  return (
    <tr className="border-b border-border/50 hover:bg-surface-overlay transition-colors">
      <td className="table-cell">
        <div className="flex items-center gap-1.5">
          <span className={cn("badge", opp.direction === "over"
            ? "bg-ev-positive-muted text-ev-positive border-ev-positive/30"
            : "bg-ev-negative-muted text-ev-negative border-ev-negative/30"
          )}>
            {opp.direction.toUpperCase()}
          </span>
          {opp.is_best_available_line && (
            <span className="badge text-2xs bg-accent/10 text-accent border-accent/30">Best</span>
          )}
        </div>
      </td>
      <td className="table-cell">
        <div className="flex flex-col gap-0.5">
          <span className="text-text-secondary">{bookmakerLabel(opp.bookmaker)}</span>
          {opp.steam_boosted && (
            <span className="text-2xs text-steam">⚡ Steam boost</span>
          )}
        </div>
      </td>
      <td className="table-cell text-right font-mono">{formatAmerican(opp.book_odds)}</td>
      <td className="table-cell text-right font-mono">{formatPct(opp.model_prob)}</td>
      <td className="table-cell text-right font-mono text-text-secondary">{formatPct(opp.implied_prob)}</td>
      <td className="table-cell text-right"><EdgeBadge edge={opp.edge} /></td>
      <td className="table-cell text-right"><EVBadge ev={opp.ev} tier={opp.tier} /></td>
      <td className="table-cell">
        <span className={cn("badge text-2xs", tierBg(opp.tier))}>{opp.tier}</span>
      </td>
      <td className="table-cell min-w-[90px]">
        <ConfidenceMeter score={opp.confidence_score} size="sm" />
      </td>
    </tr>
  );
}

function LineShoppingPanel({ shopping }: { shopping: LineShopping }) {
  const hasSoftOver = shopping.soft_over_books.length > 0;
  const hasSoftUnder = shopping.soft_under_books.length > 0;

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Line Shopping</h2>
        <div className="flex items-center gap-2">
          {shopping.line_dispersion != null && (
            <span className="text-2xs font-mono text-text-muted">
              ±{shopping.line_dispersion.toFixed(2)} spread
            </span>
          )}
          {(hasSoftOver || hasSoftUnder) && (
            <span className="badge text-2xs bg-ev-neutral/20 text-ev-neutral border-ev-neutral/30">
              {shopping.soft_over_books.length + shopping.soft_under_books.length} soft lines
            </span>
          )}
        </div>
      </div>

      {/* Best available highlight */}
      <div className="px-4 py-3 border-b border-border grid grid-cols-2 gap-4">
        <div>
          <p className="text-2xs text-text-muted uppercase tracking-wide mb-1">Best OVER</p>
          {shopping.best_over_book ? (
            <div className="flex items-center gap-2">
              <span className="font-medium text-ev-positive">{bookmakerLabel(shopping.best_over_book)}</span>
              <span className="font-mono text-text-secondary text-sm">
                {shopping.best_over_odds ? formatAmerican(shopping.best_over_odds) : "—"}
              </span>
            </div>
          ) : <span className="text-text-muted">—</span>}
        </div>
        <div>
          <p className="text-2xs text-text-muted uppercase tracking-wide mb-1">Best UNDER</p>
          {shopping.best_under_book ? (
            <div className="flex items-center gap-2">
              <span className="font-medium text-ev-negative">{bookmakerLabel(shopping.best_under_book)}</span>
              <span className="font-mono text-text-secondary text-sm">
                {shopping.best_under_odds ? formatAmerican(shopping.best_under_odds) : "—"}
              </span>
            </div>
          ) : <span className="text-text-muted">—</span>}
        </div>
      </div>

      {/* Soft book alerts */}
      {(hasSoftOver || hasSoftUnder) && (
        <div className="px-4 py-3 border-b border-border bg-ev-neutral/5">
          <p className="text-2xs font-medium text-ev-neutral mb-2">STALE LINES DETECTED</p>
          {hasSoftOver && (
            <p className="text-xs text-text-secondary">
              <span className="font-medium">Over:</span> {shopping.soft_over_books.map(bookmakerLabel).join(", ")} — below sharp consensus by ≥2.5pp
            </p>
          )}
          {hasSoftUnder && (
            <p className="text-xs text-text-secondary mt-0.5">
              <span className="font-medium">Under:</span> {shopping.soft_under_books.map(bookmakerLabel).join(", ")} — above sharp consensus by ≥2.5pp
            </p>
          )}
        </div>
      )}

      {/* All books table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="table-head">Book</th>
              <th className="table-head text-right">Line</th>
              <th className="table-head text-right">Over</th>
              <th className="table-head text-right">Under</th>
              <th className="table-head text-right">No-Vig Over%</th>
              <th className="table-head">Type</th>
            </tr>
          </thead>
          <tbody>
            {shopping.book_details.map((b) => {
              const isSoftOver = shopping.soft_over_books.includes(b.bookmaker);
              const isSoftUnder = shopping.soft_under_books.includes(b.bookmaker);
              return (
                <tr key={b.bookmaker} className="border-b border-border/50 hover:bg-surface-overlay">
                  <td className="table-cell font-medium">
                    <div className="flex items-center gap-1.5">
                      {bookmakerLabel(b.bookmaker)}
                      {b.is_sharp && <span className="badge text-2xs bg-accent-muted text-accent border-accent/30">Sharp</span>}
                    </div>
                  </td>
                  <td className="table-cell text-right font-mono">{b.line}</td>
                  <td className="table-cell text-right font-mono">
                    <span className={b.bookmaker === shopping.best_over_book ? "text-ev-positive font-semibold" : "text-text-secondary"}>
                      {formatAmerican(b.odds_over)}
                    </span>
                  </td>
                  <td className="table-cell text-right font-mono">
                    <span className={b.bookmaker === shopping.best_under_book ? "text-ev-negative font-semibold" : "text-text-secondary"}>
                      {formatAmerican(b.odds_under)}
                    </span>
                  </td>
                  <td className="table-cell text-right font-mono text-text-secondary">
                    {formatPct(b.no_vig_prob_over)}
                  </td>
                  <td className="table-cell">
                    {b.is_sharp ? (
                      <span className="text-2xs text-accent">Sharp</span>
                    ) : isSoftOver || isSoftUnder ? (
                      <span className="text-2xs text-ev-neutral">Soft</span>
                    ) : (
                      <span className="text-2xs text-text-muted">Soft</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ModelProbRow({ label, prob, weight, isPrimary }: {
  label: string; prob: number; weight: number; isPrimary?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-40 flex-shrink-0">
        <p className={cn("text-xs", isPrimary ? "font-semibold text-text-primary" : "text-text-secondary")}>{label}</p>
        {!isPrimary && <p className="text-2xs text-text-muted">Weight: {(weight * 100).toFixed(0)}%</p>}
      </div>
      <div className="flex-1 bg-border rounded-full h-1.5 overflow-hidden">
        <div className={cn("h-full rounded-full", isPrimary ? "bg-accent" : "bg-text-muted")} style={{ width: `${prob * 100}%` }} />
      </div>
      <span className={cn("font-mono text-sm w-12 text-right", isPrimary ? "text-accent font-semibold" : "text-text-secondary")}>
        {formatPct(prob)}
      </span>
    </div>
  );
}

function WhyThisBet({ prop }: { prop: any }) {
  const items: { label: string; value: string; highlight?: boolean }[] = [
    { label: "Rolling Avg (5G)", value: prop.rolling_avg_5 != null ? prop.rolling_avg_5.toFixed(1) : "—" },
    { label: "Rolling Avg (10G)", value: prop.rolling_avg_10 != null ? prop.rolling_avg_10.toFixed(1) : "—" },
    { label: "Std Dev (10G)", value: prop.rolling_std_10 != null ? prop.rolling_std_10.toFixed(1) : "—" },
    {
      label: "Hit Rate vs Line",
      value: prop.hit_rate_line != null ? formatPct(prop.hit_rate_line) : "—",
      highlight: prop.hit_rate_line != null && prop.hit_rate_line >= 0.6,
    },
    { label: "Opp. Defense", value: prop.opp_def_rank_pct != null ? defRankLabel(prop.opp_def_rank_pct) : "—" },
    {
      label: "Sharp vs Soft Dev",
      value: prop.sharp_soft_deviation != null ? `${(prop.sharp_soft_deviation * 100).toFixed(2)}pp` : "—",
      highlight: prop.sharp_soft_deviation != null && Math.abs(prop.sharp_soft_deviation) >= 0.02,
    },
  ];

  const hasSteamBoost = prop.ev_opportunities?.some((o: any) => o.steam_boosted);

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Why This Bet?</h2>
      </div>
      <div className="p-4 space-y-3">
        {hasSteamBoost && (
          <div className="bg-steam/5 border border-steam/20 rounded p-2.5 text-xs text-steam">
            ⚡ Steam signal active — confidence boosted
          </div>
        )}
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-xs text-text-muted">{item.label}</span>
            <span className={cn("text-xs font-mono font-medium", item.highlight ? "text-ev-positive" : "text-text-secondary")}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SteamPanel({ alerts }: { alerts: any[] }) {
  return (
    <div className="card border-steam/30">
      <div className="card-header bg-steam/5">
        <h2 className="card-title text-steam">⚡ Steam Detected</h2>
      </div>
      <div className="p-4 space-y-3">
        {alerts.map((a: any) => (
          <div key={a.id} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-text-primary">
                {a.direction.toUpperCase()} — {a.line_delta.toFixed(1)} pt move
              </span>
              <span className="text-text-muted">{a.velocity.toFixed(2)} pts/min</span>
            </div>
            <div className="text-2xs text-text-muted">
              {a.books_moved.map(bookmakerLabel).join(", ")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
