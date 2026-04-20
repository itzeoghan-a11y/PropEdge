"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { searchPlayers, swrKeys } from "@/lib/api";
import { cn, formatSport } from "@/lib/utils";
import type { PlayerDetail, Sport } from "@/lib/types";

const SPORTS: { value: Sport; label: string }[] = [
  { value: "basketball_nba", label: "NBA" },
  { value: "americanfootball_nfl", label: "NFL" },
  { value: "baseball_mlb", label: "MLB" },
  { value: "icehockey_nhl", label: "NHL" },
];

export default function PlayersPage() {
  const router = useRouter();
  const [sport, setSport] = useState<Sport | undefined>();
  const [query, setQuery] = useState("");

  const { data: players, isLoading } = useSWR(
    swrKeys.players(query || undefined, sport),
    () => searchPlayers(query || undefined, sport),
    { refreshInterval: 60_000 },
  );

  return (
    <div className="flex flex-col h-full">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold">Players</h1>
            <p className="text-xs text-text-muted mt-0.5">Search players · View game logs · Active props</p>
          </div>
          <span className="text-xs text-text-muted">
            {players ? `${players.length} players` : ""}
          </span>
        </div>
      </header>

      {/* Search + filters */}
      <div className="border-b border-border px-6 py-3 flex items-center gap-4 flex-wrap">
        <input
          type="search"
          placeholder="Search player name…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          className="bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary w-64 focus:outline-none focus:border-accent placeholder-text-muted"
        />
        <div className="flex items-center gap-1">
          <button
            className={cn("px-2.5 py-1 rounded text-xs border transition-all", !sport ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary")}
            onClick={() => setSport(undefined)}
          >All</button>
          {SPORTS.map(s => (
            <button
              key={s.value}
              className={cn("px-2.5 py-1 rounded text-xs border transition-all", sport === s.value ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-overlay border-border text-text-secondary")}
              onClick={() => setSport(sport === s.value ? undefined : s.value)}
            >{s.label}</button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {isLoading ? (
          <div className="grid grid-cols-4 gap-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="card p-4 space-y-2 animate-pulse">
                <div className="w-10 h-10 rounded-lg bg-surface-overlay" />
                <div className="h-3.5 bg-surface-overlay rounded w-3/4" />
                <div className="h-3 bg-surface-overlay rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : !players?.length ? (
          <div className="flex items-center justify-center h-48 text-text-muted text-sm">
            No players found. Players appear once odds are collected.
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {players.map(player => (
              <PlayerCard
                key={player.id}
                player={player}
                onClick={() => router.push(`/players/${player.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PlayerCard({ player, onClick }: { player: PlayerDetail; onClick: () => void }) {
  const isInjured = player.injury_status !== "active";
  return (
    <div
      onClick={onClick}
      className="card p-4 cursor-pointer hover:border-accent/40 hover:bg-surface-overlay transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-surface-overlay border border-border flex items-center justify-center text-base font-bold text-text-muted group-hover:text-text-primary flex-shrink-0">
          {player.name.charAt(0)}
        </div>
        <div className="min-w-0">
          <p className="font-medium text-text-primary text-sm truncate group-hover:text-accent transition-colors">
            {player.name}
          </p>
          <p className="text-2xs text-text-muted mt-0.5">{player.team} · {player.position}</p>
          <div className="flex items-center gap-1.5 mt-1.5">
            <span className="badge text-2xs bg-surface-overlay text-text-muted border-border">
              {formatSport(player.sport)}
            </span>
            {isInjured && (
              <span className="badge text-2xs bg-ev-negative-muted text-ev-negative border-ev-negative/30">
                {player.injury_status}
              </span>
            )}
            {player.active_props.length > 0 && (
              <span className="badge text-2xs bg-accent/10 text-accent border-accent/30">
                {player.active_props.length} prop{player.active_props.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
