"use client";

import { useState } from "react";
import useSWR from "swr";
import { FiltersBar } from "@/components/dashboard/FiltersBar";
import { PropsTable } from "@/components/dashboard/PropsTable";
import { getProps, getPerformance, swrKeys } from "@/lib/api";
import type { PropFilter, AnalyticsPerformance } from "@/lib/types";
import { formatPct } from "@/lib/utils";

export default function Dashboard() {
  const [filter, setFilter] = useState<PropFilter>({ min_ev: 0.03, min_confidence: 50 });

  const {
    data: props,
    isLoading,
    error,
  } = useSWR(swrKeys.props(filter), () => getProps({ ...filter, limit: 100 }), {
    refreshInterval: 30_000,
    dedupingInterval: 10_000,
  });

  const { data: perf } = useSWR(swrKeys.performance(), getPerformance, {
    refreshInterval: 60_000,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-text-primary">Dashboard</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Real-time +EV player props · Updates every 30s
            </p>
          </div>
          <LiveIndicator />
        </div>
      </header>

      {/* Stats bar */}
      {perf && <StatsBar perf={perf} count={props?.length ?? 0} />}

      {/* Filters */}
      <div className="border-b border-border px-6 py-3">
        <FiltersBar filter={filter} onChange={setFilter} />
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden">
        <PropsTable
          props={props ?? []}
          loading={isLoading}
          error={error}
        />
      </div>
    </div>
  );
}

function StatsBar({ perf, count }: { perf: AnalyticsPerformance; count: number }) {
  return (
    <div className="border-b border-border px-6 py-3 flex items-center gap-8">
      <StatItem
        label="EV Props Today"
        value={String(count)}
        highlight
      />
      <StatItem
        label="Win Rate (All-Time)"
        value={perf.overall_win_rate ? formatPct(perf.overall_win_rate) : "—"}
      />
      <StatItem
        label="Weekly Opportunities"
        value={String(perf.weekly_ev_opportunities)}
      />
      <StatItem
        label="Steam Alerts (7d)"
        value={String(perf.weekly_steam_alerts)}
      />
      <StatItem
        label="Resolved Bets"
        value={String(perf.total_resolved_bets)}
      />
    </div>
  );
}

function StatItem({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="stat-block">
      <span className="stat-label">{label}</span>
      <span className={highlight ? "stat-value text-ev-positive" : "stat-value"}>{value}</span>
    </div>
  );
}

function LiveIndicator() {
  return (
    <div className="flex items-center gap-2 text-2xs text-text-muted">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ev-positive opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-ev-positive" />
      </span>
      Live
    </div>
  );
}
