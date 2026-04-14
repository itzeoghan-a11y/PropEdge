export type Sport = "basketball_nba" | "americanfootball_nfl" | "baseball_mlb" | "icehockey_nhl";
export type Tier = "standard" | "high" | "elite";
export type Direction = "over" | "under";
export type SubscriptionTier = "free" | "pro" | "elite";

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  tier: SubscriptionTier;
  subscription_status: string;
  has_active_subscription: boolean;
  daily_prop_limit: number | null;
  alert_min_ev: number;
  alert_min_confidence: number;
  alert_steam: boolean;
}

export interface PropSummary {
  id: number;
  player_id: number;
  player_name: string;
  sport: Sport;
  stat_type: string;
  line: number;
  game_date: string;
  opponent_team: string;
  best_direction: Direction | null;
  best_bookmaker: string | null;
  best_book_odds: number | null;
  model_prob: number | null;
  implied_prob: number | null;
  edge: number | null;
  ev: number | null;
  confidence: number | null;
  tier: Tier | null;
  sharp_prob: number | null;
  has_steam: boolean;
  is_overdue: boolean;
}

export interface EVOpportunity {
  id: number;
  direction: Direction;
  bookmaker: string;
  book_odds: number;
  implied_prob: number;
  model_prob: number;
  edge: number;
  ev: number;
  confidence_score: number;
  tier: Tier;
  sharp_prob: number | null;
  sharp_deviation: number | null;
  found_at: string;
}

export interface OddsRow {
  bookmaker: string;
  line: number;
  odds_over: number;
  odds_under: number;
  implied_prob_over: number;
  is_sharp: boolean;
  recorded_at: string;
}

export interface ModelBreakdown {
  distribution_prob: number | null;
  bayesian_prob: number | null;
  ml_prob: number | null;
  sharp_prob: number | null;
  final_prob_over: number;
  confidence: number;
  model_agreement: number;
  n_models: number;
  weights_used: Record<string, number>;
}

export interface SteamAlert {
  id: number;
  direction: Direction;
  books_moved: string[];
  line_before: number;
  line_after: number;
  line_delta: number;
  velocity: number;
  detected_at: string;
}

export interface PropDetail {
  id: number;
  player_id: number;
  player_name: string;
  sport: Sport;
  stat_type: string;
  line: number;
  game_date: string;
  opponent_team: string;
  ev_opportunities: EVOpportunity[];
  model_breakdown: ModelBreakdown | null;
  latest_odds: OddsRow[];
  steam_alerts: SteamAlert[];
  rolling_avg_5: number | null;
  rolling_avg_10: number | null;
  rolling_std_10: number | null;
  hit_rate_line: number | null;
  opp_def_rank_pct: number | null;
  sharp_soft_deviation: number | null;
  sample_size: number;
}

export interface GameLog {
  game_date: string;
  opponent_team: string;
  is_home: boolean;
  minutes_played: number | null;
  points: number | null;
  rebounds: number | null;
  assists: number | null;
  three_pointers_made: number | null;
  steals: number | null;
  blocks: number | null;
  passing_yards: number | null;
  rushing_yards: number | null;
  receiving_yards: number | null;
  receptions: number | null;
  usage_rate: number | null;
}

export interface PlayerDetail {
  id: number;
  name: string;
  sport: Sport;
  team: string;
  team_abbr: string;
  position: string;
  injury_status: string;
  game_logs: GameLog[];
  active_props: Array<{
    id: number;
    stat_type: string;
    line: number;
    game_date: string;
    opponent_team: string;
  }>;
}

export interface PropFilter {
  sport?: Sport;
  stat_type?: string;
  min_ev?: number;
  min_confidence?: number;
  bookmaker?: string;
  tier?: Tier;
  direction?: Direction;
}

export interface AnalyticsPerformance {
  total_resolved_bets: number;
  overall_win_rate: number | null;
  weekly_ev_opportunities: number;
  weekly_steam_alerts: number;
}
