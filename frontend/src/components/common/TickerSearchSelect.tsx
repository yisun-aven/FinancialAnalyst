/**
 * TickerSearchSelect — region picker + live ticker search in one component.
 *
 * Usage:
 *   <TickerSearchSelect
 *     value={{ region: 'TW', ticker: '2330.TW' }}
 *     onChange={(v) => console.log(v.region, v.ticker, v.name)}
 *     disabled={false}
 *   />
 */
import { useState, useRef, useCallback } from 'react'
import { Select, Space, Typography, Tag, Spin } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { REGIONS, REGION_MAP } from '../../config/regions'

const { Text } = Typography
const API_BASE = 'http://localhost:8000'

export interface TickerValue {
  region: string
  ticker: string
  name?: string
}

interface SearchResult {
  symbol: string
  name: string
  exchange: string
  type: string
}

interface Props {
  value?: TickerValue
  onChange?: (val: TickerValue) => void
  disabled?: boolean
}

export default function TickerSearchSelect({ value, onChange, disabled }: Props) {
  const [region, setRegion] = useState<string>(value?.region ?? 'US')
  const [options, setOptions] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleRegionChange = (r: string) => {
    setRegion(r)
    setOptions([])
    // Clear ticker when region changes (to avoid cross-region mismatch)
    onChange?.({ region: r, ticker: '', name: '' })
  }

  const handleSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (!q || q.length < 1) {
        setOptions([])
        return
      }
      debounceRef.current = setTimeout(async () => {
        setSearching(true)
        try {
          const params = new URLSearchParams({ q, region })
          const res = await fetch(`${API_BASE}/api/search?${params}`)
          if (res.ok) {
            const data: SearchResult[] = await res.json()
            setOptions(data)
          }
        } finally {
          setSearching(false)
        }
      }, 300)
    },
    [region]
  )

  const handleSelect = (symbol: string) => {
    const found = options.find((o) => o.symbol === symbol)
    onChange?.({ region, ticker: symbol, name: found?.name ?? '' })
  }

  const regionCfg = REGION_MAP[region]

  // The selected value label shown in the trigger (compact — symbol + truncated name)
  const selectedLabel = value?.ticker
    ? (() => {
        const found = options.find((o) => o.symbol === value.ticker)
        const name = found?.name ?? value.name ?? ''
        const truncated = name.length > 22 ? name.slice(0, 22) + '…' : name
        return (
          <Space size={6}>
            <Text strong style={{ fontSize: 13 }}>{value.ticker}</Text>
            {truncated && <Text style={{ fontSize: 12, color: '#4a5060' }}>{truncated}</Text>}
          </Space>
        )
      })()
    : undefined

  // Options list — full name shown in dropdown rows only
  const selectOptions = options.map((o) => ({
    value: o.symbol,
    // label is what shows in the trigger after selection — keep it compact
    label: o.symbol,
    searchText: `${o.symbol} ${o.name}`.toLowerCase(),
  }))

  return (
    <Space.Compact style={{ width: '100%' }}>
      {/* Region picker */}
      <Select
        value={region}
        onChange={handleRegionChange}
        disabled={disabled}
        style={{ width: 148, flexShrink: 0 }}
        popupMatchSelectWidth={false}
        suffixIcon={<GlobalOutlined />}
        options={REGIONS.map((r) => ({
          value: r.key,
          label: (
            <Space size={5}>
              <span>{r.flag}</span>
              <span style={{ fontSize: 12 }}>{r.label}</span>
            </Space>
          ),
        }))}
        optionRender={(opt) => (
          <Space size={6}>
            <span style={{ fontSize: 16 }}>{REGION_MAP[opt.value as string]?.flag}</span>
            <Space direction="vertical" size={0}>
              <Text style={{ fontSize: 13 }}>{REGION_MAP[opt.value as string]?.label}</Text>
              <Text style={{ fontSize: 11, color: '#8a909e' }}>{REGION_MAP[opt.value as string]?.exchangeName}</Text>
            </Space>
          </Space>
        )}
      />

      {/* Ticker search */}
      <Select
        showSearch
        value={value?.ticker || undefined}
        labelRender={() => selectedLabel ?? <span style={{ color: '#bfbfbf' }}>{regionCfg ? `Search ${regionCfg.exchangeName}…` : 'Search ticker…'}</span>}
        placeholder={regionCfg ? `Search ${regionCfg.exchangeName}…` : 'Search ticker…'}
        filterOption={false}
        onSearch={handleSearch}
        onSelect={handleSelect}
        disabled={disabled}
        notFoundContent={
          searching
            ? <Spin size="small" style={{ display: 'block', textAlign: 'center', padding: 8 }} />
            : <Text style={{ fontSize: 12, color: '#8a909e', padding: '8px 12px', display: 'block' }}>
                Type to search {regionCfg?.exchangeName ?? 'exchange'}
              </Text>
        }
        options={selectOptions}
        style={{ flex: 1, minWidth: 0 }}
        popupMatchSelectWidth={360}
        optionRender={(opt) => {
          const o = options.find((x) => x.symbol === opt.value)
          if (!o) return <Text>{opt.value}</Text>
          return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0, overflow: 'hidden' }}>
                <Text strong style={{ fontSize: 13, flexShrink: 0 }}>{o.symbol}</Text>
                <Text style={{ fontSize: 12, color: '#4a5060', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {o.name}
                </Text>
              </div>
              <Tag color="default" style={{ fontSize: 10, padding: '0 4px', flexShrink: 0, marginLeft: 'auto' }}>
                {o.type}
              </Tag>
            </div>
          )
        }}
      />
    </Space.Compact>
  )
}
