import type { RunSummary, RunDetail, ReportSummary, ReportDetail } from '../types/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  getRuns: () => get<RunSummary[]>('/api/runs'),
  getRun: (filename: string) => get<RunDetail>(`/api/runs/${encodeURIComponent(filename)}`),
  getReports: () => get<ReportSummary[]>('/api/reports'),
  getReport: (filename: string) => get<ReportDetail>(`/api/reports/${encodeURIComponent(filename)}`),
}
