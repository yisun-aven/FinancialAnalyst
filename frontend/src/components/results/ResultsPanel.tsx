import { useState } from 'react'
import { Empty, Typography, Alert, Tag, Space, Button } from 'antd'
import { TrophyOutlined, CheckCircleFilled, DownOutlined, UpOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { usePipelineStore } from '../../store/pipelineStore'
import TickerResultCard from './TickerResultCard'

const { Text } = Typography

const summaryStyles = `
  .summary-md { font-size: 13px; line-height: 1.65; color: #1f3a2e; }
  .summary-md p { margin: 0 0 8px; }
  .summary-md p:last-child { margin-bottom: 0; }
  .summary-md strong { color: #0f3b24; font-weight: 600; }
  .summary-md em { color: #3d5a4a; font-style: italic; }
  .summary-md ul, .summary-md ol { margin: 4px 0 8px; padding-left: 20px; }
  .summary-md li { margin-bottom: 3px; }
  .summary-md h1, .summary-md h2, .summary-md h3, .summary-md h4 { font-size: 13px; margin: 8px 0 4px; color: #0f3b24; font-weight: 700; }
  .summary-md code { font-family: monospace; font-size: 12px; background: #ffffff80; padding: 1px 5px; border-radius: 3px; color: #0f3b24; }
  .summary-md table { border-collapse: collapse; margin: 6px 0; font-size: 12px; width: 100%; }
  .summary-md th, .summary-md td { border: 1px solid #b7e4c7; padding: 4px 8px; text-align: left; }
  .summary-md th { background: #ffffff70; }
`

const COLLAPSED_MAX_HEIGHT = 180

export default function ResultsPanel() {
  const allResults = usePipelineStore((s) => s.allResults)
  const tickersSucceeded = usePipelineStore((s) => s.tickersSucceeded)
  const tickersFailed = usePipelineStore((s) => s.tickersFailed)
  const summary = usePipelineStore((s) => s.summary)
  const status = usePipelineStore((s) => s.status)
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const isLongSummary = (summary?.length ?? 0) > 480

  const baseTickers = tickersSucceeded.length > 0
    ? tickersSucceeded
    : Object.keys(allResults)

  // If the synthesis step produced a conviction_score, re-order the tickers
  // so the highest-conviction name renders first.
  const tickers = [...baseTickers].sort((a, b) => {
    const sa = allResults[a]?.synthesis?.conviction_score
    const sb = allResults[b]?.synthesis?.conviction_score
    if (typeof sa === 'number' && typeof sb === 'number') return sb - sa
    if (typeof sa === 'number') return -1
    if (typeof sb === 'number') return 1
    return 0
  })

  if (status === 'idle' || (status !== 'complete' && tickers.length === 0)) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Empty
          image={<TrophyOutlined style={{ fontSize: 40, color: '#dde1e7' }} />}
          description={<Text style={{ color: '#8a909e' }}>No results yet — run an analysis first</Text>}
        />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 20 }}>
      <style>{summaryStyles}</style>
      {summary && (
        <div
          style={{
            marginBottom: 16,
            padding: '12px 14px 12px 14px',
            background: '#f0faf4',
            border: '1px solid #b7e4c7',
            borderRadius: 8,
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
          }}
        >
          <CheckCircleFilled style={{ color: '#16a34a', fontSize: 16, marginTop: 2, flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <Text style={{
              fontSize: 10, color: '#0f3b24', fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.08em',
              display: 'block', marginBottom: 6,
            }}>
              Executive Summary
            </Text>
            <div
              className="summary-md"
              style={{
                maxHeight: isLongSummary && !summaryExpanded ? COLLAPSED_MAX_HEIGHT : 'none',
                overflow: 'hidden',
                position: 'relative',
                WebkitMaskImage:
                  isLongSummary && !summaryExpanded
                    ? 'linear-gradient(to bottom, #000 70%, transparent 100%)'
                    : 'none',
                maskImage:
                  isLongSummary && !summaryExpanded
                    ? 'linear-gradient(to bottom, #000 70%, transparent 100%)'
                    : 'none',
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
            </div>
            {isLongSummary && (
              <Button
                type="link"
                size="small"
                icon={summaryExpanded ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setSummaryExpanded((v) => !v)}
                style={{ padding: 0, marginTop: 4, color: '#0f9960', fontSize: 12 }}
              >
                {summaryExpanded ? 'Show less' : 'Show more'}
              </Button>
            )}
          </div>
        </div>
      )}

      {tickersFailed.length > 0 && (
        <Alert
          message={
            <Space>
              <Text style={{ fontSize: 13 }}>Failed tickers:</Text>
              {tickersFailed.map((t) => <Tag key={t} color="red">{t}</Tag>)}
            </Space>
          }
          type="warning"
          style={{ marginBottom: 16 }}
        />
      )}

      {tickers.map((ticker) => {
        const results = allResults[ticker]
        if (!results) return null
        return <TickerResultCard key={ticker} ticker={ticker} results={results} />
      })}
    </div>
  )
}
