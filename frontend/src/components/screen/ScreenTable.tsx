import { Table, Tag, Typography, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { BarChartOutlined } from '@ant-design/icons'
import { usePipelineStore } from '../../store/pipelineStore'
import type { ScreenStock } from '../../types/events'

const { Text } = Typography

function fmt(v: number | null | undefined, decimals = 1, suffix = '') {
  if (v == null) return <Text style={{ color: '#8a909e' }}>—</Text>
  return `${v.toFixed(decimals)}${suffix}`
}

function colorNum(v: number | null | undefined, good: 'positive' | 'negative' = 'positive') {
  if (v == null) return <Text style={{ color: '#8a909e' }}>—</Text>
  const isGood = good === 'positive' ? v > 0 : v < 0
  return <Text style={{ color: isGood ? '#16a34a' : '#dc2626', fontFamily: 'monospace' }}>{v > 0 ? '+' : ''}{v.toFixed(1)}%</Text>
}

const columns: ColumnsType<ScreenStock> = [
  {
    title: 'Ticker',
    dataIndex: 'ticker',
    key: 'ticker',
    fixed: 'left',
    width: 90,
    render: (v: string) => <Text strong style={{ color: '#4f6ef7', fontFamily: 'monospace' }}>{v}</Text>,
  },
  {
    title: 'Company',
    dataIndex: 'company_name',
    key: 'company_name',
    width: 180,
    ellipsis: true,
    render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
  },
  {
    title: 'Score',
    dataIndex: 'score',
    key: 'score',
    width: 80,
    sorter: (a, b) => (a.score ?? 0) - (b.score ?? 0),
    defaultSortOrder: 'descend',
    render: (v: number) => (
      <Tag color={v >= 70 ? 'green' : v >= 50 ? 'gold' : 'red'} style={{ fontFamily: 'monospace', fontWeight: 700 }}>
        {v.toFixed(0)}
      </Tag>
    ),
  },
  {
    title: 'Price',
    dataIndex: 'current_price',
    key: 'current_price',
    width: 90,
    sorter: (a, b) => (a.current_price ?? 0) - (b.current_price ?? 0),
    render: (v: number, r) => <Text style={{ fontFamily: 'monospace' }}>{r.currency === 'USD' ? '$' : ''}{v?.toFixed(2)}</Text>,
  },
  {
    title: 'Mkt Cap ($B)',
    dataIndex: 'market_cap_b',
    key: 'market_cap_b',
    width: 110,
    sorter: (a, b) => (a.market_cap_b ?? 0) - (b.market_cap_b ?? 0),
    render: (v: number) => <Text style={{ fontFamily: 'monospace' }}>{fmt(v, 1)}</Text>,
  },
  {
    title: 'P/E',
    dataIndex: 'pe_ratio',
    key: 'pe_ratio',
    width: 70,
    sorter: (a, b) => (a.pe_ratio ?? 9999) - (b.pe_ratio ?? 9999),
    render: (v) => <Text style={{ fontFamily: 'monospace' }}>{fmt(v, 1)}</Text>,
  },
  {
    title: 'P/B',
    dataIndex: 'pb_ratio',
    key: 'pb_ratio',
    width: 70,
    sorter: (a, b) => (a.pb_ratio ?? 9999) - (b.pb_ratio ?? 9999),
    render: (v) => <Text style={{ fontFamily: 'monospace' }}>{fmt(v, 1)}</Text>,
  },
  {
    title: 'EV/EBITDA',
    dataIndex: 'ev_ebitda',
    key: 'ev_ebitda',
    width: 100,
    sorter: (a, b) => (a.ev_ebitda ?? 9999) - (b.ev_ebitda ?? 9999),
    render: (v) => <Text style={{ fontFamily: 'monospace' }}>{fmt(v, 1)}</Text>,
  },
  {
    title: 'FCF Yield',
    dataIndex: 'fcf_yield_pct',
    key: 'fcf_yield_pct',
    width: 95,
    sorter: (a, b) => (a.fcf_yield_pct ?? -999) - (b.fcf_yield_pct ?? -999),
    render: (v) => colorNum(v),
  },
  {
    title: 'Rev Growth',
    dataIndex: 'revenue_growth_pct',
    key: 'revenue_growth_pct',
    width: 105,
    sorter: (a, b) => (a.revenue_growth_pct ?? -999) - (b.revenue_growth_pct ?? -999),
    render: (v) => colorNum(v),
  },
  {
    title: 'PE Discount',
    dataIndex: 'pe_discount_pct',
    key: 'pe_discount_pct',
    width: 105,
    sorter: (a, b) => (a.pe_discount_pct ?? -999) - (b.pe_discount_pct ?? -999),
    render: (v) => colorNum(v),
  },
  {
    title: 'Sector',
    dataIndex: 'sector',
    key: 'sector',
    width: 160,
    ellipsis: true,
    render: (v: string) => <Text style={{ fontSize: 11, color: '#4a5060' }}>{v}</Text>,
  },
  {
    title: 'Exchange',
    dataIndex: 'exchange',
    key: 'exchange',
    width: 90,
    render: (v: string) => <Text style={{ fontSize: 11, color: '#8a909e' }}>{v}</Text>,
  },
]

export default function ScreenTable() {
  const screenResults = usePipelineStore((s) => s.screenResults)

  if (!screenResults.length) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Empty
          image={<BarChartOutlined style={{ fontSize: 40, color: '#dde1e7' }} />}
          description={
            <Text style={{ color: '#8a909e' }}>No screen results yet — run a Discover scan</Text>
          }
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 20, height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <BarChartOutlined style={{ color: '#4f6ef7' }} />
        <Text strong>{screenResults.length} stocks screened</Text>
        <Tag color="blue">{screenResults.filter((s) => s.score >= 70).length} high score</Tag>
      </div>
      <Table
        dataSource={screenResults}
        columns={columns}
        rowKey="ticker"
        size="small"
        scroll={{ x: 1200 }}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `${t} stocks` }}
        style={{ fontSize: 12 }}
      />
    </div>
  )
}
