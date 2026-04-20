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
  discord_webhook: string | null;
  phone_number: string | null;
}

export interface BookDetail {
  bookmaker: string;
  line: number;
  odds_over: number;
  odds_under: number;
  no_vig_prob_over: number;
  is_sharp: boolean;
}

export interface LineShopping {
  best_over_book: string | null;
  best_over_odds: number | null;
  best_under_book: string | null;
  best_under_odds: number | null;
  sharp_line: number | null;
  sharp_no_vig_prob_over: number | null;
  consensus_line: number | null;
  consensus_no_vig_prob_over: number | null;
  line_dispersion: number | null;
  prob_dispersion: number | null;
  soft_over_books: string[];
  soft_under_books: string[];
  book_details: BookDetail[];
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
  // Line shopping
  best_over_book: string | null;
  best_over_odds: number | null;
  best_under_book: string | null;
  best_under_odds: number | null;
  consensus_line: number | null;
  line_dispersion: number | null;
  soft_book_count: number | null;
  // Status
  has_steam: boolean;
  steam_boosted: boolean;
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
  is_best_available_line: boolean;
  steam_boosted: boolean;
  line_at_flag: number | null;
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
  line_shopping: LineShopping | null;
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
  best_available_only?: boolean;
  has_steam?: boolean;
}

export interface AnalyticsPerformance {
  total_resolved_bets: number;
  overall_win_rate: number | null;
  weekly_ev_opportunities: number;
  weekly_steam_alerts: number;
}

export interface BetRecord {
  id: number;
  prop_id: number;
  player_name: string;
  sport: string;
  stat_type: string;
  line: number;
  direction: Direction;
  bookmaker: string;
  book_odds: number;
  model_prob: number;
  implied_prob: number;
  edge: number;
  ev: number;
  confidence: number;
  tier: Tier;
  sharp_prob: number | null;
  is_best_available_line: boolean;
  steam_boosted: boolean;
  found_at: string;
  game_date: string;
  actual_result: number | null;
  resolved: boolean;
  won: boolean | null;
  pnl: number | null;
  closing_line_odds: number | null;
  clv: number | null;
}

export interface BetHistorySummary {
  total_flagged: number;
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  total_pnl: number;
  roi: number | null;
}

export interface BetHistory {
  bets: BetRecord[];
  summary: BetHistorySummary;
}

export interface BacktestResult {
  n_bets: number;
  win_rate: number;
  roi: number;
  avg_ev: number;
  avg_confidence: number;
  brier_score: number;
  tier_breakdown: Record<string, { n: number; win_rate: number; roi: number }>;
  book_breakdown: Record<string, { n: number; win_rate: number; roi: number }>;
}
