import { useEffect } from 'react'
import { List, Typography, Tag, Empty, Tooltip } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import { api } from '../../api/rest'
import { usePipelineStore } from '../../store/pipelineStore'

const { Text } = Typography

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

/** Parses "2026-04-12_18-07-45" → "Apr 12  18:07" */
function formatTs(ts: string): string {
  if (ts.length >= 16) {
    const datePart = ts.slice(0, 10)   // "2026-04-12"
    const timePart = ts.slice(11, 16)  // "18-07"
    const [, mm, dd] = datePart.split('-')
    const monthName = MONTHS[parseInt(mm, 10) - 1] ?? mm
    return `${monthName} ${parseInt(dd, 10)}  ${timePart.replace('-', ':')}`
  }
  return ts
}

export default function PastRunsList() {
  const pastRuns = usePipelineStore((s) => s.pastRuns)
  const setPastRuns = usePipelineStore((s) => s.setPastRuns)
  const loadRunDetail = usePipelineStore((s) => s.loadRunDetail)
  const setActiveTab = usePipelineStore((s) => s.setActiveTab)
  const status = usePipelineStore((s) => s.status)

  // Load on mount
  useEffect(() => {
    api.getRuns().then(setPastRuns).catch(() => {})
  }, [setPastRuns])

  // Refresh list whenever a pipeline completes
  useEffect(() => {
    if (status === 'complete') {
      setTimeout(() => {
        api.getRuns().then(setPastRuns).catch(() => {})
      }, 800)
    }
  }, [status, setPastRuns])

  const handleLoad = async (filename: string, reportFilename: string) => {
    try {
      const [detail, report] = await Promise.all([
        api.getRun(filename),
        reportFilename ? api.getReport(reportFilename).catch(() => null) : Promise.resolve(null),
      ])
      loadRunDetail(
        detail.all_results,
        detail.tickers_succeeded,
        reportFilename,
        report?.content ?? undefined,
      )
      setActiveTab('results')
    } catch {
      // silently fail
    }
  }

  if (!pastRuns.length) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={<Text style={{ fontSize: 12, color: '#8a909e' }}>No past runs</Text>}
        style={{ margin: '12px 0' }}
      />
    )
  }

  return (
    <List
      size="small"
      dataSource={pastRuns}
      renderItem={(run) => (
        <List.Item
          style={{ padding: '6px 0', cursor: 'pointer', borderBottom: '1px solid #e8eaed' }}
          onClick={() => handleLoad(run.filename, run.report_filename)}
        >
          <div style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
              <HistoryOutlined style={{ color: '#8a909e', fontSize: 11 }} />
              <Text style={{ fontSize: 11, color: '#4a5060' }}>{formatTs(run.run_ts)}</Text>
              <Text style={{ fontSize: 10, color: '#8a909e', marginLeft: 'auto' }}>
                {run.size_kb.toFixed(1)} KB
              </Text>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {run.tickers.slice(0, 6).map((t) => (
                <Tag key={t} style={{ fontSize: 10, padding: '0 4px', margin: 0 }} color="blue">
                  {t}
                </Tag>
              ))}
              {run.tickers.length > 6 && (
                <Tooltip title={run.tickers.slice(6).join(', ')}>
                  <Tag style={{ fontSize: 10, padding: '0 4px', margin: 0 }}>
                    +{run.tickers.length - 6}
                  </Tag>
                </Tooltip>
              )}
            </div>
          </div>
        </List.Item>
      )}
    />
  )
}
