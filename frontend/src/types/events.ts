// ── Base envelope ─────────────────────────────────────────────────────────
export interface WsEnvelope {
  type: string
  agent?: string
  ticker?: string | null
  message?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any
  timestamp?: string
}

// ── Keepalive ─────────────────────────────────────────────────────────────
export interface PingEvent {
  type: 'ping'
}

// ── Pipeline stage ────────────────────────────────────────────────────────
export interface PipelineStageData {
  stage: number
  name: string
  total_stages: number
}
export interface PipelineStageEvent extends WsEnvelope {
  type: 'pipeline_stage'
  data: PipelineStageData
}

// ── Agent lifecycle ───────────────────────────────────────────────────────
export interface AgentStartData { name: string }
export interface AgentCompleteData { duration: number }
export interface AgentStartEvent extends WsEnvelope { type: 'agent_start'; data: AgentStartData }
export interface AgentCompleteEvent extends WsEnvelope { type: 'agent_complete'; data: AgentCompleteData }
export interface AgentTickerStartEvent extends WsEnvelope { type: 'agent_ticker_start' }
export interface AgentTickerCompleteEvent extends WsEnvelope { type: 'agent_ticker_complete'; data: Record<string, unknown> }

// ── Claude call lifecycle ─────────────────────────────────────────────────
export interface ClaudeCallStartData { model: string; max_tokens: number; has_tools: boolean }
export interface ClaudeCallCompleteData { input_tokens: number; output_tokens: number; duration: number }
export interface ClaudeCallStartEvent extends WsEnvelope { type: 'claude_call_start'; data: ClaudeCallStartData }
export interface ClaudeCallCompleteEvent extends WsEnvelope { type: 'claude_call_complete'; data: ClaudeCallCompleteData }
export interface RateLimitWaitData { attempt: number; wait_seconds: number }
export interface RateLimitWaitEvent extends WsEnvelope { type: 'rate_limit_wait'; data: RateLimitWaitData }

// ── Screener events ───────────────────────────────────────────────────────
export interface UniverseLoadedData { universe: string; count: number }
export interface ScreenerStartData { total: number; top_n: number }
export interface ScreenerProgressData { completed: number; total: number; pct: number }
export interface ScreenerCompleteData { screened: number; top_n: number; top_tickers: string[] }

export interface ScreenStock {
  ticker: string
  score: number
  company_name: string
  sector: string
  country: string
  exchange: string
  currency: string
  current_price: number
  market_cap_b: number
  pe_ratio: number | null
  pb_ratio: number | null
  ev_ebitda: number | null
  fcf_yield_pct: number | null
  revenue_growth_pct: number | null
  sector_pe_median: number | null
  pe_discount_pct: number | null
}

export interface ScreenResultsData {
  stocks: ScreenStock[]
  top_tickers: string[]
}

// ── Report ready ──────────────────────────────────────────────────────────
export interface ReportReadyData {
  report_path: string
  report_filename: string
  summary: string
}
export interface ReportReadyEvent extends WsEnvelope { type: 'report_ready'; data: ReportReadyData }

// ── Pipeline terminal ─────────────────────────────────────────────────────
export interface PipelineCompleteData {
  report_path: string
  report_filename: string
  results_filename: string
  tickers_succeeded: string[]
  tickers_failed: string[]
  summary: string
  screen_results?: ScreenStock[]
  all_results?: Record<string, AllResults>
}
export interface PipelineCompleteEvent extends WsEnvelope { type: 'pipeline_complete'; data: PipelineCompleteData }

export interface PipelineErrorData { error: string }
export interface PipelineErrorEvent extends WsEnvelope { type: 'pipeline_error'; data: PipelineErrorData }

// ── Per-ticker agent output shapes ────────────────────────────────────────
export interface CashFlowQuality { quality: 'high' | 'medium' | 'low'; [k: string]: unknown }

export interface FundamentalResult {
  valuation_verdict?: string
  confidence?: 'high' | 'medium' | 'low'
  current_price?: number
  market_cap_b?: number
  pe_ratio?: number | null
  ev_ebitda?: number | null
  dcf_intrinsic_value?: number | null
  dcf_margin_of_safety?: number | null
  peg_ratio?: number | null
  pfcf_ratio?: number | null
  target_price_bear?: number | null
  target_price_base?: number | null
  target_price_bull?: number | null
  buy_below_price?: number | null
  cash_flow_quality?: CashFlowQuality
  reasoning?: string
  key_risks?: string[]
  key_strengths?: string[]
  entry_strategy?: string
  target_price_rationale?: string
  return_on_equity_pct?: number | null
}

export interface GrowthResult {
  growth_verdict?: string
  growth_quality_score?: number
  revenue_cagr_3y_pct?: number | null
  eps_cagr_3y_pct?: number | null
  fcf_cagr_3y_pct?: number | null
  peg_ratio?: number | null
  revenue_trend?: string
  reasoning?: string
  growth_catalysts?: string[]
  growth_risks?: string[]
}

export interface PeerResult {
  peer_verdict?: string
  composite_peer_discount_pct?: number | null
  company_pe_discount_pct?: number | null
  sector_median_pe?: number | null
  sector?: string
  peers_used?: string[]
  reasoning?: string
  peer_comparison_note?: string
}

export interface TechnicalResult {
  technical_verdict?: string
  rsi_14?: number | null
  ma_50?: number | null
  ma_200?: number | null
  cross_signal?: string
  position_52w?: number | null
  volume_ratio?: number | null
  entry_signal?: string
  reasoning?: string
  technical_risks?: string[]
}

export interface SentimentResult {
  sentiment_score?: number | null
  sentiment_label?: string
  analyst_consensus?: string
  insider_activity?: string
  top_headlines?: Array<{ title: string; date: string; sentiment?: string }>
  reasoning?: string
}

export interface AllResults {
  fundamental?: FundamentalResult
  growth?: GrowthResult
  peers?: PeerResult
  technical?: TechnicalResult
  sentiment?: SentimentResult
  raw?: Record<string, unknown>
}

// ── Union of all typed events ─────────────────────────────────────────────
export type AnyWsEvent =
  | PingEvent
  | PipelineStageEvent
  | AgentStartEvent
  | AgentCompleteEvent
  | AgentTickerStartEvent
  | AgentTickerCompleteEvent
  | ClaudeCallStartEvent
  | ClaudeCallCompleteEvent
  | RateLimitWaitEvent
  | ReportReadyEvent
  | PipelineCompleteEvent
  | PipelineErrorEvent
  | WsEnvelope
