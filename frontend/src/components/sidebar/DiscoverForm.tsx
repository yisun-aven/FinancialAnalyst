import { useState } from 'react'
import { Button, Select, InputNumber, Space, Typography, Slider, Alert } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useWebSocket } from '../../api/websocket'
import { usePipelineStore } from '../../store/pipelineStore'

const { Text } = Typography

const UNIVERSES = [
  { value: 'sp500', label: 'S&P 500' },
  { value: 'nasdaq100', label: 'Nasdaq 100' },
  { value: 'russell2000', label: 'Russell 2000' },
  { value: 'global_large_cap', label: 'Global Large Cap' },
  { value: 'asia_pacific', label: 'Asia Pacific' },
  { value: 'europe_stoxx600', label: 'Europe STOXX 600' },
]

const SECTORS = [
  'Technology', 'Healthcare', 'Financials', 'Consumer Discretionary',
  'Industrials', 'Communication Services', 'Consumer Staples',
  'Energy', 'Utilities', 'Real Estate', 'Materials',
]

const REGIONS = [
  { value: 'north_america', label: 'North America' },
  { value: 'europe', label: 'Europe' },
  { value: 'asia_pacific', label: 'Asia Pacific' },
  { value: 'emerging_markets', label: 'Emerging Markets' },
  { value: 'global', label: 'Global' },
]

export default function DiscoverForm() {
  const [universe, setUniverse] = useState('sp500')
  const [topN, setTopN] = useState(10)
  const [minMarketCap, setMinMarketCap] = useState(1)
  const [sectors, setSectors] = useState<string[]>([])
  const [region, setRegion] = useState<string | undefined>()

  const { connect } = useWebSocket()
  const status = usePipelineStore((s) => s.status)
  const errorMessage = usePipelineStore((s) => s.errorMessage)
  const isRunning = status === 'running'

  const handleRun = () => {
    connect('/ws/screen', {
      universe,
      top_n: topN,
      min_market_cap_b: minMarketCap,
      ...(sectors.length ? { sectors } : {}),
      ...(region ? { region } : {}),
    })
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Universe
        </Text>
        <Select
          style={{ width: '100%', marginTop: 6 }}
          value={universe}
          onChange={setUniverse}
          options={UNIVERSES}
          disabled={isRunning}
        />
      </div>

      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Top N stocks to analyse
        </Text>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
          <Slider
            style={{ flex: 1 }}
            min={3}
            max={25}
            value={topN}
            onChange={setTopN}
            disabled={isRunning}
          />
          <InputNumber
            style={{ width: 60 }}
            min={3}
            max={25}
            value={topN}
            onChange={(v) => setTopN(v ?? 10)}
            disabled={isRunning}
          />
        </div>
      </div>

      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Min market cap ($B)
        </Text>
        <InputNumber
          style={{ width: '100%', marginTop: 6 }}
          min={0}
          step={0.5}
          value={minMarketCap}
          onChange={(v) => setMinMarketCap(v ?? 1)}
          disabled={isRunning}
        />
      </div>

      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Sectors (optional)
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%', marginTop: 6 }}
          placeholder="All sectors"
          value={sectors}
          onChange={setSectors}
          options={SECTORS.map((s) => ({ value: s, label: s }))}
          maxTagCount="responsive"
          disabled={isRunning}
        />
      </div>

      <div>
        <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Region (optional)
        </Text>
        <Select
          style={{ width: '100%', marginTop: 6 }}
          placeholder="All regions"
          allowClear
          value={region}
          onChange={setRegion}
          options={REGIONS}
          disabled={isRunning}
        />
      </div>

      {status === 'error' && (
        <Alert message={errorMessage ?? 'Error'} type="error" showIcon style={{ fontSize: 12 }} />
      )}

      <Button
        type="primary"
        icon={<SearchOutlined />}
        block
        onClick={handleRun}
        loading={isRunning}
        disabled={isRunning}
      >
        {isRunning ? 'Screening…' : 'Screen & Analyse'}
      </Button>
    </Space>
  )
}
