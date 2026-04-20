import { useState } from 'react'
import { Button, Space, Tag, Typography, Alert } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import { useWebSocket } from '../../api/websocket'
import { usePipelineStore } from '../../store/pipelineStore'
import TickerSearchSelect, { type TickerValue } from '../common/TickerSearchSelect'
import { REGION_MAP } from '../../config/regions'

const { Text } = Typography

// Region-specific quick-add presets. Keep the list short and representative
// (index bellwethers + AI value-chain names) so first-time users have obvious
// starting points without having to type anything.
const QUICK_ADDS: Record<string, { ticker: string; label: string }[]> = {
  US: [
    { ticker: 'AAPL',   label: 'Apple' },
    { ticker: 'MSFT',   label: 'Microsoft' },
    { ticker: 'GOOGL',  label: 'Alphabet' },
    { ticker: 'AMZN',   label: 'Amazon' },
    { ticker: 'NVDA',   label: 'NVIDIA' },
    { ticker: 'META',   label: 'Meta' },
    { ticker: 'TSLA',   label: 'Tesla' },
    { ticker: 'BRK-B',  label: 'Berkshire B' },
  ],
  TW: [
    { ticker: '2330.TW', label: 'TSMC' },
    { ticker: '2317.TW', label: 'Foxconn' },
    { ticker: '2454.TW', label: 'MediaTek' },
    { ticker: '2308.TW', label: 'Delta Electronics' },
    { ticker: '2303.TW', label: 'UMC' },
    { ticker: '3711.TW', label: 'ASE Technology' },
    { ticker: '2881.TW', label: 'Fubon Financial' },
    { ticker: '2412.TW', label: 'Chunghwa Telecom' },
  ],
}

export default function ManualRunForm() {
  const [region, setRegion] = useState<string>('US')
  const [tickers, setTickers] = useState<string[]>([])
  const [names, setNames] = useState<Record<string, string>>({})
  const { connect } = useWebSocket()
  const status = usePipelineStore((s) => s.status)
  const errorMessage = usePipelineStore((s) => s.errorMessage)
  const isRunning = status === 'running'

  const addTicker = (raw: string, name?: string) => {
    const cleaned = raw.trim().toUpperCase()
    if (!cleaned || tickers.includes(cleaned)) return
    setTickers((prev) => [...prev, cleaned])
    if (name) setNames((prev) => ({ ...prev, [cleaned]: name }))
  }

  const removeTicker = (t: string) => {
    setTickers((prev) => prev.filter((x) => x !== t))
    setNames((prev) => {
      const { [t]: _removed, ...rest } = prev
      return rest
    })
  }

  const handleSelection = (v: TickerValue) => {
    if (v.region !== region) setRegion(v.region)
    if (v.ticker) addTicker(v.ticker, v.name)
  }

  const handleRun = () => {
    if (!tickers.length) return
    connect('/ws/run', { tickers })
  }

  const quickAdds = QUICK_ADDS[region] ?? []
  const regionCfg = REGION_MAP[region]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      {/* Region + ticker search */}
      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Pick region & search ticker
        </Text>
        <div style={{ marginTop: 6 }}>
          <TickerSearchSelect
            value={{ region, ticker: '' }}
            onChange={handleSelection}
            disabled={isRunning}
          />
        </div>
        {regionCfg && (
          <Text style={{ fontSize: 11, color: '#8a909e', marginTop: 4, display: 'block' }}>
            Searching {regionCfg.exchangeName}
          </Text>
        )}
      </div>

      {/* Quick-add presets (region-specific) */}
      {quickAdds.length > 0 && (
        <div>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Quick add
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
            {quickAdds.map(({ ticker, label }) => {
              const isSelected = tickers.includes(ticker)
              return (
                <Tag
                  key={ticker}
                  style={{ cursor: 'pointer', fontSize: 11, padding: '2px 6px' }}
                  color={isSelected ? 'blue' : 'default'}
                  onClick={() => (isSelected ? removeTicker(ticker) : addTicker(ticker, label))}
                  title={label}
                >
                  {/* Symbol + tiny company name so .TW codes are decipherable */}
                  <span style={{ fontWeight: 600 }}>{ticker.replace(/\.TW$/, '').replace(/\.TWO$/, '')}</span>
                  <span style={{ color: isSelected ? '#4f6ef7' : '#8a909e', marginLeft: 4 }}>
                    {label}
                  </span>
                </Tag>
              )
            })}
          </div>
        </div>
      )}

      {/* Selected tickers */}
      {tickers.length > 0 && (
        <div>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Selected ({tickers.length})
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
            {tickers.map((t) => (
              <Tag
                key={t}
                closable
                onClose={() => removeTicker(t)}
                color="blue"
                style={{ fontSize: 12, padding: '2px 8px' }}
              >
                <span style={{ fontWeight: 600 }}>{t}</span>
                {names[t] && (
                  <span style={{ color: '#4a5060', marginLeft: 4, fontSize: 11 }}>
                    · {names[t]}
                  </span>
                )}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {status === 'error' && (
        <Alert
          message={errorMessage ?? 'Error'}
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
