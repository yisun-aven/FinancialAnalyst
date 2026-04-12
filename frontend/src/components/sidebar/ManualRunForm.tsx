import { useState } from 'react'
import { Button, Input, Space, Tag, Typography, Alert } from 'antd'
import { PlayCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useWebSocket } from '../../api/websocket'
import { usePipelineStore } from '../../store/pipelineStore'

const { Text } = Typography

const COMMON_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B']

export default function ManualRunForm() {
  const [inputVal, setInputVal] = useState('')
  const [tickers, setTickers] = useState<string[]>([])
  const { connect } = useWebSocket()
  const status = usePipelineStore((s) => s.status)

  const addTicker = (raw: string) => {
    const cleaned = raw.trim().toUpperCase().replace(/[^A-Z0-9.^-]/g, '')
    if (cleaned && !tickers.includes(cleaned)) {
      setTickers((prev) => [...prev, cleaned])
    }
    setInputVal('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTicker(inputVal)
    }
  }

  const removeTicker = (t: string) => setTickers((prev) => prev.filter((x) => x !== t))

  const handleRun = () => {
    if (!tickers.length) return
    connect('/ws/run', { tickers })
  }

  const isRunning = status === 'running'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Quick add
        </Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          {COMMON_TICKERS.map((t) => (
            <Tag
              key={t}
              style={{ cursor: 'pointer', fontSize: 11 }}
              color={tickers.includes(t) ? 'blue' : 'default'}
              onClick={() => (tickers.includes(t) ? removeTicker(t) : addTicker(t))}
            >
              {t}
            </Tag>
          ))}
        </div>
      </div>

      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Custom tickers
        </Text>
        <Input
          style={{ marginTop: 6 }}
          placeholder="e.g. TSM, 005930.KS"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          suffix={
            <PlusOutlined
              style={{ cursor: 'pointer', color: '#4f6ef7' }}
              onClick={() => addTicker(inputVal)}
            />
          }
          disabled={isRunning}
        />
        <Text style={{ fontSize: 11, color: '#8a909e' }}>Press Enter or comma to add</Text>
      </div>

      {tickers.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {tickers.map((t) => (
            <Tag key={t} closable onClose={() => removeTicker(t)} color="blue" style={{ fontSize: 12 }}>
              {t}
            </Tag>
          ))}
        </div>
      )}

      {status === 'error' && (
        <Alert
          message={usePipelineStore.getState().errorMessage ?? 'Error'}
          type="error"
          showIcon
          style={{ fontSize: 12 }}
        />
      )}

      <Button
        type="primary"
        icon={<PlayCircleOutlined />}
        block
        onClick={handleRun}
        loading={isRunning}
        disabled={!tickers.length || isRunning}
      >
        {isRunning ? 'Running…' : `Analyse ${tickers.length ? `(${tickers.length})` : ''}`}
      </Button>
    </Space>
  )
}
