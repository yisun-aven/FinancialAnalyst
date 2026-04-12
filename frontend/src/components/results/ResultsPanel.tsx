import { Empty, Typography, Alert, Tag, Space } from 'antd'
import { TrophyOutlined } from '@ant-design/icons'
import { usePipelineStore } from '../../store/pipelineStore'
import TickerResultCard from './TickerResultCard'

const { Text } = Typography

export default function ResultsPanel() {
  const allResults = usePipelineStore((s) => s.allResults)
  const tickersSucceeded = usePipelineStore((s) => s.tickersSucceeded)
  const tickersFailed = usePipelineStore((s) => s.tickersFailed)
  const summary = usePipelineStore((s) => s.summary)
  const status = usePipelineStore((s) => s.status)

  const tickers = tickersSucceeded.length > 0
    ? tickersSucceeded
    : Object.keys(allResults)

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
      {summary && (
        <Alert
          message={summary}
          type="success"
          showIcon
          style={{ marginBottom: 16, fontSize: 13 }}
        />
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
