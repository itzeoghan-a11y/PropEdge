"use client";

import { use, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  ReferenceLine,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import { getPlayerDetail, swrKeys } from "@/lib/api";
import { formatSport, formatStatType, cn } from "@/lib/utils";
import type { GameLog } from "@/lib/types";

const STAT_OPTIONS = [
  { key: "points", label: "Points" },
  { key: "rebounds", label: "Rebounds" },
  { key: "assists", label: "Assists" },
  { key: "three_pointers_made", label: "3PM" },
  { key: "passing_yards", label: "Pass Yds" },
  { key: "rushing_yards", label: "Rush Yds" },
  { key: "receiving_yards", label: "Rec Yds" },
  { key: "receptions", label: "Receptions" },
];

export default function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useSWR(swrKeys.player(Number(id)), () =>
    getPlayerDetail(Number(id))
  );

  const [activeStat, setActiveStat] = useState<string | null>(null);

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64 text-text-secondary text-sm">
        Loading…
      </div>
    );
  }

  // Determine available stats from game logs
  const availableStats = STAT_OPTIONS.filter((s) =>
    data.game_logs.some((g: GameLog) => (g as any)[s.key] != null)
  );

  const selectedStat = activeStat ?? availableStats[0]?.key ?? "points";

  const chartData = data.game_logs.slice(0, 15).map((g: GameLog, i: number) => ({
    name: `${g.opponent_team} (${g.is_home ? "H" : "A"})`,
    value: (g as any)[selectedStat] ?? 0,
    date: g.game_date,
  })).reverse();

  const avg = chartData.length
    ? chartData.reduce((s, d) => s + d.value, 0) / chartData.length
    : 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-text-muted">
        <Link href="/" className="hover:text-text-secondary transition-colors">Dashboard</Link>
        <span>/</span>
        <span className="text-text-secondary">Players</span>
        <span>/</span>
        <span className="text-text-secondary">{data.name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-lg bg-surface-overlay border border-border flex items-center justify-center text-lg font-bold text-text-muted">
          {data.name.charAt(0)}
        </div>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{data.name}</h1>
            <span className="badge bg-surface-overlay text-text-secondary border-border">
              {formatSport(data.sport)}
            </span>
            {data.injury_status !== "active" && (
              <span className="badge bg-ev-negative-muted text-ev-negative border-ev-negative/30">
                {data.injury_status.toUpperCase()}
              </span>
            )}
          </div>
          <p className="text-text-secondary text-sm mt-0.5">
            {data.team} · {data.position}
          </p>
        </div>
      </div>

      {/* Active props */}
      {data.active_props.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Active Props</h2>
          </div>
          <div className="flex flex-wrap gap-3 p-4">
            {data.active_props.map((p: any) => (
              <Link
                key={p.id}
                href={`/props/${p.id}`}
                className="bg-surface-overlay border border-border rounded-lg px-3 py-2 hover:border-accent/40 transition-all group"
              >
                <p className="text-xs font-medium text-text-secondary group-hover:text-accent transition-colors">
                  {formatStatType(p.stat_type)}
                </p>
                <p className="text-lg font-mono font-semibold">{p.line}</p>
                <p className="text-2xs text-text-muted">{p.game_date} vs {p.opponent_team}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Game log chart */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Performance (Last 15 Games)</h2>
          <div className="flex items-center gap-1">
            {availableStats.map((s) => (
              <button
                key={s.key}
                className={cn(
                  "px-2.5 py-1 rounded text-xs border transition-all",
                  s.key === selectedStat
                    ? "bg-accent/15 border-accent/40 text-accent"
                    : "bg-surface-overlay border-border text-text-secondary hover:text-text-primary",
                )}
                onClick={() => setActiveStat(s.key)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4 h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
              <XAxis
                dataKey="name"
                tick={{ fontSize: 9, fill: "#5a5d72" }}
                tickLine={false}
                axisLine={{ stroke: "#2a2d3a" }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#5a5d72" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#1a1d26",
                  border: "1px solid #2a2d3a",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#e8eaf0",
                }}
                cursor={{ fill: "#2a2d3a" }}
              />
              <ReferenceLine y={avg} stroke="#3b82f6" strokeDasharray="3 3" strokeWidth={1.5} />
              <Bar dataKey="value" radius={[2, 2, 0, 0]} maxBarSize={28}>
                {chartData.map((entry, idx) => (
                  <Cell
                    key={idx}
                    fill={entry.value >= avg ? "#22c55e" : "#ef4444"}
                    opacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="px-4 pb-3 flex items-center gap-4">
          <div className="stat-block">
            <span className="stat-label">Avg ({chartData.length}G)</span>
            <span className="stat-value">{avg.toFixed(1)}</span>
          </div>
          <div className="stat-block">
            <span className="stat-label">Max</span>
            <span className="stat-value">{Math.max(...chartData.map(d => d.value)).toFixed(1)}</span>
          </div>
          <div className="stat-block">
            <span className="stat-label">Min</span>
            <span className="stat-value">{Math.min(...chartData.map(d => d.value)).toFixed(1)}</span>
          </div>
        </div>
      </div>

      {/* Game log table */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Game Log</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="table-head">Date</th>
                <th className="table-head">Opp</th>
                <th className="table-head">H/A</th>
                <th className="table-head text-right">MIN</th>
                <th className="table-head text-right">PTS</th>
                <th className="table-head text-right">REB</th>
                <th className="table-head text-right">AST</th>
                <th className="table-head text-right">3PM</th>
                <th className="table-head text-right">USG%</th>
              </tr>
            </thead>
            <tbody>
              {data.game_logs.slice(0, 20).map((g: GameLog) => (
                <tr key={g.game_date + g.opponent_team} className="border-b border-border/50 hover:bg-surface-overlay transition-colors">
                  <td className="table-cell font-mono text-xs text-text-secondary">{g.game_date}</td>
                  <td className="table-cell text-text-primary">{g.opponent_team}</td>
                  <td className="table-cell text-text-muted text-xs">{g.is_home ? "H" : "A"}</td>
                  <td className="table-cell text-right font-mono text-text-secondary">{g.minutes_played?.toFixed(0) ?? "—"}</td>
                  <td className="table-cell text-right font-mono font-medium">{g.points ?? "—"}</td>
                  <td className="table-cell text-right font-mono text-text-secondary">{g.rebounds ?? "—"}</td>
                  <td className="table-cell text-right font-mono text-text-secondary">{g.assists ?? "—"}</td>
                  <td className="table-cell text-right font-mono text-text-secondary">{g.three_pointers_made ?? "—"}</td>
                  <td className="table-cell text-right font-mono text-text-secondary">
                    {g.usage_rate ? `${g.usage_rate.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
