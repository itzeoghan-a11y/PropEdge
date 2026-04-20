"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  PieChart, Pie, Legend,
} from "recharts";
import { getPerformance, runBacktest, getBacktestHistory, swrKeys } from "@/lib/api";
import { cn, formatPct, formatSport, formatStatType } from "@/lib/utils";
import type { BacktestResult, Sport } from "@/lib/types";

function dateStr(d: Date) {
  return d.toISOString().split("T")[0];
}

const TOOLTIP_STYLE = {
  background: "#1a1d26", border: "1px solid #2a2d3a",
  borderRadius: 6, fontSize: 12, color: "#e8eaf0",
};

export default function AnalyticsPage() {
  const { data: perf } = useSWR(swrKeys.performance(), getPerformance, { refreshInterval: 60_000 });

  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return dateStr(d);
  });
  const [dateTo] = useState(() => dateStr(new Date()));
  const [sport, setSport] = useState<Sport | undefined>();
  const [minEdge, setMinEdge] = useState(0.03);
  const [minConf, setMinConf] = useState(50);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: history } = useSWR(["backtest-history"], getBacktestHistory);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const r = await runBacktest({ date_from: dateFrom, date_to: dateTo, sport, min_edge: minEdge, min_confidence: minConf });
      setResult(r as BacktestResult);
    } catch (e: any) {
      setError(e.message ?? "Backtest failed");
    } finally {
      setRunning(false);
    }
  }

  const tierChartData = result
    ? Object.entries(result.tier_breakdown).map(([tier, d]) => ({
        name: tier, win_rate: d.win_rate, roi: d.roi, n: d.n,
      }))
    : [];

  const bookChartData = result
    ? Object.entries(result.book_breakdown).map(([book, d]) => ({
        name: book, win_rate: d.win_rate, roi: d.roi, n: d.n,
      }))
    : [];

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
      <header>
        <h1 className="text-base font-semibold">Analytics</h1>
        <p className="text-xs text-text-muted mt-0.5">Platform performance · Backtest resolved bets</p>
      </header>

      {/* Platform stats */}
      {perf && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Resolved Bets" value={String(perf.total_resolved_bets)} />
          <StatCard
            label="Overall Win Rate"
            value={perf.overall_win_rate != null ? formatPct(perf.overall_win_rate) : "—"}
            color={perf.overall_win_rate != null && perf.overall_win_rate >= 0.52 ? "text-ev-positive" : "text-text-primary"}
          />
          <StatCard label="EV Opps (7d)" value={String(perf.weekly_ev_opportunities)} />
          <StatCard label="Steam Alerts (7d)" value={String(perf.weekly_steam_alerts)} />
        </div>
      )}

      {/* Backtest config */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Backtest Configuration</h2>
          <span className="text-2xs text-text-muted">Pro+ feature</span>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Date From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Date To</label>
              <input
                type="date"
                value={dateTo}
                readOnly
                className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-muted"
              />
            </div>
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Sport</label>
              <select
                value={sport ?? ""}
                onChange={e => setSport((e.target.value as Sport) || undefined)}
                className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              >
                <option value="">All Sports</option>
                <option value="basketball_nba">NBA</option>
                <option value="americanfootball_nfl">NFL</option>
                <option value="baseball_mlb">MLB</option>
                <option value="icehockey_nhl">NHL</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Min Edge</label>
              <select
                value={minEdge}
                onChange={e => setMinEdge(parseFloat(e.target.value))}
                className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              >
                <option value={0.02}>2%</option>
                <option value={0.03}>3%</option>
                <option value={0.05}>5%</option>
                <option value={0.08}>8%</option>
              </select>
            </div>
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Min Confidence</label>
              <select
                value={minConf}
                onChange={e => setMinConf(parseFloat(e.target.value))}
                className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              >
                <option value={40}>40+</option>
                <option value={50}>50+</option>
                <option value={60}>60+</option>
                <option value={70}>70+</option>
              </select>
            </div>
          </div>
          <button
            onClick={handleRun}
            disabled={running}
            className="px-4 py-2 bg-accent text-white rounded text-sm font-medium hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {running ? "Running…" : "Run Backtest"}
          </button>
          {error && <p className="text-xs text-ev-negative">{error}</p>}
        </div>
      </div>

      {/* Backtest results */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-5 gap-4">
            <StatCard label="Total Bets" value={String(result.n_bets)} />
            <StatCard
              label="Win Rate"
              value={formatPct(result.win_rate)}
              color={result.win_rate >= 0.52 ? "text-ev-positive" : result.win_rate < 0.48 ? "text-ev-negative" : "text-text-primary"}
            />
            <StatCard
              label="ROI"
              value={`${result.roi > 0 ? "+" : ""}${(result.roi * 100).toFixed(2)}%`}
              color={result.roi > 0 ? "text-ev-positive" : "text-ev-negative"}
            />
            <StatCard label="Avg EV" value={`${(result.avg_ev * 100).toFixed(2)}%`} />
            <StatCard
              label="Brier Score"
              value={result.brier_score.toFixed(4)}
              color={result.brier_score < 0.23 ? "text-ev-positive" : "text-text-primary"}
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-2 gap-4">
            {tierChartData.length > 0 && (
              <div className="card">
                <div className="card-header"><h3 className="card-title">Win Rate by Tier</h3></div>
                <div className="p-4 h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={tierChartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#5a5d72" }} tickLine={false} axisLine={false} />
                      <YAxis tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "#5a5d72" }} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${(v*100).toFixed(1)}%`]} />
                      <Bar dataKey="win_rate" radius={[3, 3, 0, 0]} maxBarSize={40}>
                        {tierChartData.map((d, i) => (
                          <Cell key={i} fill={d.name === "elite" ? "#a855f7" : d.name === "high" ? "#3b82f6" : "#22c55e"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
            {bookChartData.length > 0 && (
              <div className="card">
                <div className="card-header"><h3 className="card-title">ROI by Book</h3></div>
                <div className="p-4 h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={bookChartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#5a5d72" }} tickLine={false} axisLine={false} />
                      <YAxis tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "#5a5d72" }} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${(v*100).toFixed(1)}%`]} />
                      <Bar dataKey="roi" radius={[3, 3, 0, 0]} maxBarSize={40}>
                        {bookChartData.map((d, i) => (
                          <Cell key={i} fill={d.roi >= 0 ? "#22c55e" : "#ef4444"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {/* Tier breakdown table */}
          {tierChartData.length > 0 && (
            <div className="card">
              <div className="card-header"><h3 className="card-title">Tier Breakdown</h3></div>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="table-head">Tier</th>
                    <th className="table-head text-right">Bets</th>
                    <th className="table-head text-right">Win Rate</th>
                    <th className="table-head text-right">ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {tierChartData.map(d => (
                    <tr key={d.name} className="border-b border-border/50">
                      <td className="table-cell">
                        <span className={cn("badge text-2xs capitalize",
                          d.name === "elite" ? "bg-elite/10 text-elite border-elite/30" :
                          d.name === "high" ? "bg-high/10 text-high border-high/30" :
                          "bg-ev-positive-muted text-ev-positive border-ev-positive/30"
                        )}>{d.name}</span>
                      </td>
                      <td className="table-cell text-right font-mono">{d.n}</td>
                      <td className="table-cell text-right font-mono">
                        <span className={d.win_rate >= 0.52 ? "text-ev-positive" : "text-text-secondary"}>{formatPct(d.win_rate)}</span>
                      </td>
                      <td className="table-cell text-right font-mono">
                        <span className={d.roi >= 0 ? "text-ev-positive" : "text-ev-negative"}>{d.roi >= 0 ? "+" : ""}{(d.roi * 100).toFixed(2)}%</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Backtest history */}
      {Array.isArray(history) && history.length > 0 && (
        <div className="card">
          <div className="card-header"><h3 className="card-title">Recent Backtest Runs</h3></div>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="table-head">Label</th>
                <th className="table-head">Period</th>
                <th className="table-head text-right">Bets</th>
                <th className="table-head text-right">Win Rate</th>
                <th className="table-head text-right">ROI</th>
                <th className="table-head text-right">Brier</th>
              </tr>
            </thead>
            <tbody>
              {(history as any[]).map(r => (
                <tr key={r.id} className="border-b border-border/50">
                  <td className="table-cell text-text-secondary">{r.label}</td>
                  <td className="table-cell font-mono text-xs text-text-muted">{r.date_from} → {r.date_to}</td>
                  <td className="table-cell text-right font-mono">{r.total_bets}</td>
                  <td className="table-cell text-right font-mono">{formatPct(r.win_rate)}</td>
                  <td className="table-cell text-right font-mono">
                    <span className={r.roi >= 0 ? "text-ev-positive" : "text-ev-negative"}>
                      {r.roi >= 0 ? "+" : ""}{(r.roi * 100).toFixed(2)}%
                    </span>
                  </td>
                  <td className="table-cell text-right font-mono text-text-muted">{r.brier_score?.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return (
    <div className="card p-4">
      <p className="text-2xs text-text-muted uppercase tracking-wide">{label}</p>
      <p className={cn("font-mono font-semibold text-lg mt-1", color)}>{value}</p>
    </div>
  );
}
