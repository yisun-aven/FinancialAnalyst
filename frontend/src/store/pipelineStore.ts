import { create } from 'zustand'
import type { WsEnvelope, ScreenStock, AllResults, PipelineCompleteData } from '../types/events'
import type { RunSummary } from '../types/api'

export type PipelineStatus = 'idle' | 'running' | 'complete' | 'error'

export interface PipelineStore {
  // Connection & status
  status: PipelineStatus
  errorMessage: string | null

  // Live feed events
  events: WsEnvelope[]

  // Screener results
  screenResults: ScreenStock[]

  // Analysis results (per ticker)
  allResults: Record<string, AllResults>
  tickersSucceeded: string[]
  tickersFailed: string[]

  // Report
  reportFilename: string | null
  reportContent: string | null
  resultsFilename: string | null
  summary: string | null

  // Active tab
  activeTab: 'feed' | 'screen' | 'results' | 'report'

  // Past runs (from REST)
  pastRuns: RunSummary[]

  // Actions
  setStatus: (s: PipelineStatus) => void
  setError: (msg: string) => void
  addEvent: (e: WsEnvelope) => void
  setScreenResults: (stocks: ScreenStock[]) => void
  setPipelineComplete: (data: PipelineCompleteData) => void
  setActiveTab: (tab: PipelineStore['activeTab']) => void
  setPastRuns: (runs: RunSummary[]) => void
  loadRunDetail: (allResults: Record<string, AllResults>, tickers: string[], report: string, content?: string) => void
  setReportContent: (content: string | null) => void
  reset: () => void
}

const initialState = {
  status: 'idle' as PipelineStatus,
  errorMessage: null,
  events: [] as WsEnvelope[],
  screenResults: [] as ScreenStock[],
  allResults: {} as Record<string, AllResults>,
  tickersSucceeded: [] as string[],
  tickersFailed: [] as string[],
  reportFilename: null,
  reportContent: null,
  resultsFilename: null,
  summary: null,
  activeTab: 'feed' as const,
  pastRuns: [] as RunSummary[],
}

export const usePipelineStore = create<PipelineStore>((set) => ({
  ...initialState,

  setStatus: (status) => set({ status }),

  setError: (errorMessage) => set({ status: 'error', errorMessage }),

  addEvent: (event) =>
    set((state) => ({ events: [...state.events, event] })),

  setScreenResults: (screenResults) => set({ screenResults }),

  setPipelineComplete: (data) =>
    set({
      status: 'complete',
      reportFilename: data.report_filename,
      resultsFilename: data.results_filename,
      tickersSucceeded: data.tickers_succeeded,
      tickersFailed: data.tickers_failed,
      summary: data.summary,
      screenResults: data.screen_results ?? [],
      allResults: data.all_results ?? {},
    }),

  setActiveTab: (activeTab) => set({ activeTab }),

  setPastRuns: (pastRuns) => set({ pastRuns }),

  loadRunDetail: (allResults, tickers, report, content) =>
    set({
      allResults,
      tickersSucceeded: tickers,
      reportFilename: report,
      reportContent: content ?? null,
      status: 'complete',
      activeTab: 'results',
    }),

  setReportContent: (reportContent) => set({ reportContent }),

  reset: () => set({ ...initialState }),
}))
