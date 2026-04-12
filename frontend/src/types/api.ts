import type { AllResults, ScreenStock } from './events'

// ── GET /api/runs ─────────────────────────────────────────────────────────
export interface RunSummary {
  filename: string
  run_ts: string
  tickers: string[]
  report_filename: string
  size_kb: number
}

// ── GET /api/runs/{filename} ──────────────────────────────────────────────
export interface RunDetail {
  run_ts: string
  tickers_succeeded: string[]
  tickers_failed: string[]
  all_results: Record<string, AllResults>
  report_filename: string
  summary: string
  screen_results: ScreenStock[]
}

// ── GET /api/reports ──────────────────────────────────────────────────────
export interface ReportSummary {
  filename: string
  date: string
  size_kb: number
}

// ── GET /api/reports/{filename} ───────────────────────────────────────────
export interface ReportDetail {
  filename: string
  content: string
}

// ── WebSocket run request ─────────────────────────────────────────────────
export interface WsRunRequest {
  tickers: string[]
  run_date?: string
}

// ── WebSocket screen request ──────────────────────────────────────────────
export interface WsScreenRequest {
  universe: string
  top_n: number
  min_market_cap_b: number
  run_date?: string
  sectors?: string[]
  region?: string
  countries?: string[]
}
