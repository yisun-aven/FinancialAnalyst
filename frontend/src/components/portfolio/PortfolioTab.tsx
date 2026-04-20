import { useEffect, useState } from 'react'
import {
  Button, InputNumber, Table, Typography, Space, Tooltip,
  Popconfirm, Form, Modal, Empty, Spin, Statistic, Card, message, Tag, Divider, DatePicker,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined,
  ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined, WalletOutlined,
  InfoCircleOutlined, HistoryOutlined, TrophyOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useUserStore } from '../../store/userStore'
import type { PortfolioPosition, SoldPosition } from '../../types/user'
import TickerSearchSelect, { type TickerValue } from '../common/TickerSearchSelect'
import { inferRegion, currencySymbolForTicker, REGION_MAP } from '../../config/regions'

const { Text, Title } = Typography

// ── Shared helpers ────────────────────────────────────────────────────────────

interface PositionPnL {
  currentPrice: number | null
  marketValue: number | null
  costBasis: number
  unrealizedPnL: number | null
  unrealizedPnLPct: number | null
  dayChange: number | null
  dayChangePct: number | null
  currencySym: string
}

function computePnL(pos: PortfolioPosition, livePrice: number | null, dayChangePct: number | null, currency?: string): PositionPnL {
  const costBasis = pos.shares * pos.avgCostBasis
  const currencySym = currencySymbolForTicker(pos.ticker, currency)
  if (livePrice === null) {
    return { currentPrice: null, marketValue: null, costBasis, unrealizedPnL: null, unrealizedPnLPct: null, dayChange: null, dayChangePct: null, currencySym }
  }
  const marketValue = pos.shares * livePrice
  const unrealizedPnL = marketValue - costBasis
  const unrealizedPnLPct = costBasis !== 0 ? (unrealizedPnL / costBasis) * 100 : null
  const dayChange = dayChangePct !== null ? marketValue * (dayChangePct / 100) : null
  return { currentPrice: livePrice, marketValue, costBasis, unrealizedPnL, unrealizedPnLPct, dayChange, dayChangePct, currencySym }
}

function PnLText({ value, pct, sym = '$' }: { value: number | null; pct?: number | null; sym?: string }) {
  if (value === null) return <Text style={{ color: '#8a909e' }}>—</Text>
  const isUp = value >= 0
  const color = isUp ? '#16a34a' : '#dc2626'
  return (
    <Space size={4}>
      {isUp ? <ArrowUpOutlined style={{ color, fontSize: 10 }} /> : <ArrowDownOutlined style={{ color, fontSize: 10 }} />}
      <Text style={{ color, fontWeight: 500 }}>
        {isUp ? '+' : '-'}{sym}{Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        {pct !== undefined && pct !== null && (
          <Text style={{ color, fontSize: 11, marginLeft: 4 }}>
            ({isUp ? '+' : ''}{pct.toFixed(2)}%)
          </Text>
        )}
      </Text>
    </Space>
  )
}

// ── Active position Add/Edit modal ────────────────────────────────────────────

interface AddEditModalProps {
  open: boolean
  initial?: PortfolioPosition | null
  onClose: () => void
}

function AddEditModal({ open, initial, onClose }: AddEditModalProps) {
  const [form] = Form.useForm()
  const addPosition = useUserStore((s) => s.addPosition)
  const updatePosition = useUserStore((s) => s.updatePosition)

  const [tickerVal, setTickerVal] = useState<TickerValue>({
    region: initial?.region ?? 'US',
    ticker: initial?.ticker ?? '',
    name: '',
  })

  const regionCfg = REGION_MAP[tickerVal.region]
  const costLabel = regionCfg ? `Avg. cost per share (${regionCfg.currencySymbol})` : 'Avg. cost per share'

  useEffect(() => {
    if (open) {
      const initRegion = initial?.region ?? inferRegion(initial?.ticker ?? '')
      setTickerVal({ region: initRegion, ticker: initial?.ticker ?? '', name: '' })
      form.setFieldsValue(
        initial
          ? { shares: initial.shares, avgCostBasis: initial.avgCostBasis, note: initial.note }
          : { shares: null, avgCostBasis: null, note: '' }
      )
    }
  }, [open, initial, form])

  const handleOk = () => {
    if (!tickerVal.ticker) { message.error('Please select a ticker'); return }
    form.validateFields().then((vals) => {
      if (initial) {
        updatePosition(initial.ticker, { shares: vals.shares, avgCostBasis: vals.avgCostBasis, note: vals.note ?? '' })
        message.success(`${initial.ticker} updated`)
      } else {
        addPosition({ ticker: tickerVal.ticker, region: tickerVal.region, shares: vals.shares, avgCostBasis: vals.avgCostBasis, note: vals.note ?? '' })
        message.success(`${tickerVal.ticker} added to portfolio`)
      }
      onClose()
    })
  }

  return (
    <Modal title={initial ? `Edit ${initial.ticker}` : 'Add Position'} open={open} onOk={handleOk} onCancel={onClose} okText={initial ? 'Save' : 'Add'} width={500}>
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="Region & Ticker" required>
          {initial ? (
            <Space>
              <Tag>{REGION_MAP[initial.region]?.flag} {REGION_MAP[initial.region]?.label}</Tag>
              <Text strong>{initial.ticker}</Text>
            </Space>
          ) : (
            <TickerSearchSelect value={tickerVal} onChange={(v) => setTickerVal(v)} />
          )}
          {tickerVal.name && (
            <Text style={{ fontSize: 12, color: '#8a909e', marginTop: 4, display: 'block' }}>{tickerVal.name}</Text>
          )}
        </Form.Item>
        <Space style={{ width: '100%' }} size={8}>
          <Form.Item name="shares" label="Shares" rules={[{ required: true, message: 'Enter number of shares' }]} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber placeholder="e.g. 10" min={0.0001} precision={4} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="avgCostBasis" label={costLabel} rules={[{ required: true, message: 'Enter your average cost' }]} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber placeholder="e.g. 150.00" min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
        </Space>
        <Form.Item name="note" label="Note" style={{ marginTop: 16 }}>
          <textarea rows={2} placeholder="Optional note…" style={{ width: '100%', padding: '4px 11px', borderRadius: 6, border: '1px solid #dde1e7', fontSize: 14, fontFamily: 'inherit', resize: 'vertical', outline: 'none' }}
            onChange={(e) => form.setFieldValue('note', e.target.value)} defaultValue={initial?.note ?? ''} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

// ── Sold position Add/Edit modal ──────────────────────────────────────────────

interface SoldModalProps {
  open: boolean
  initial?: SoldPosition | null
  onClose: () => void
}

function SoldModal({ open, initial, onClose }: SoldModalProps) {
  const [form] = Form.useForm()
  const addSoldPosition = useUserStore((s) => s.addSoldPosition)
  const updateSoldPosition = useUserStore((s) => s.updateSoldPosition)

  const [tickerVal, setTickerVal] = useState<TickerValue>({
    region: initial?.region ?? 'US',
    ticker: initial?.ticker ?? '',
    name: '',
  })

  const regionCfg = REGION_MAP[tickerVal.region]
  const currSym = regionCfg?.currencySymbol ?? '$'

  useEffect(() => {
    if (open) {
      const initRegion = initial?.region ?? inferRegion(initial?.ticker ?? '')
      setTickerVal({ region: initRegion, ticker: initial?.ticker ?? '', name: '' })
      form.setFieldsValue(
        initial
          ? { shares: initial.shares, avgCostBasis: initial.avgCostBasis, soldPrice: initial.soldPrice, soldAt: dayjs(initial.soldAt), note: initial.note }
          : { shares: null, avgCostBasis: null, soldPrice: null, soldAt: dayjs(), note: '' }
      )
    }
  }, [open, initial, form])

  const handleOk = () => {
    if (!tickerVal.ticker) { message.error('Please select a ticker'); return }
    form.validateFields().then((vals) => {
      const payload = {
        ticker: tickerVal.ticker,
        region: tickerVal.region,
        shares: vals.shares,
        avgCostBasis: vals.avgCostBasis,
        soldPrice: vals.soldPrice,
        soldAt: (vals.soldAt as dayjs.Dayjs).toISOString(),
        note: vals.note ?? '',
      }
      if (initial) {
        updateSoldPosition(initial.id, payload)
        message.success(`${initial.ticker} sale updated`)
      } else {
        addSoldPosition(payload)
        message.success(`${tickerVal.ticker} sale recorded`)
      }
      onClose()
    })
  }

  return (
    <Modal title={initial ? `Edit sale — ${initial.ticker}` : 'Record Sold Position'} open={open} onOk={handleOk} onCancel={onClose} okText={initial ? 'Save' : 'Record Sale'} width={520}>
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="Region & Ticker" required>
          {initial ? (
            <Space>
              <Tag>{REGION_MAP[initial.region]?.flag} {REGION_MAP[initial.region]?.label}</Tag>
              <Text strong>{initial.ticker}</Text>
            </Space>
          ) : (
            <TickerSearchSelect value={tickerVal} onChange={(v) => setTickerVal(v)} />
          )}
          {tickerVal.name && (
            <Text style={{ fontSize: 12, color: '#8a909e', marginTop: 4, display: 'block' }}>{tickerVal.name}</Text>
          )}
        </Form.Item>

        <Space style={{ width: '100%' }} size={8}>
          <Form.Item name="shares" label="Shares sold" rules={[{ required: true, message: 'Enter shares' }]} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber placeholder="e.g. 10" min={0.0001} precision={4} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="soldAt" label="Date sold" rules={[{ required: true, message: 'Enter date' }]} style={{ flex: 1, marginBottom: 0 }}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Space>

        <Space style={{ width: '100%', marginTop: 12 }} size={8}>
          <Form.Item name="avgCostBasis" label={`Avg buy price (${currSym})`} rules={[{ required: true, message: 'Enter buy price' }]} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber placeholder="e.g. 120.00" min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="soldPrice" label={`Sell price (${currSym})`} rules={[{ required: true, message: 'Enter sell price' }]} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber placeholder="e.g. 180.00" min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
        </Space>

        <Form.Item name="note" label="Note" style={{ marginTop: 12 }}>
          <textarea rows={2} placeholder="Optional note…" style={{ width: '100%', padding: '4px 11px', borderRadius: 6, border: '1px solid #dde1e7', fontSize: 14, fontFamily: 'inherit', resize: 'vertical', outline: 'none' }}
            onChange={(e) => form.setFieldValue('note', e.target.value)} defaultValue={initial?.note ?? ''} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

// ── Stats card row ────────────────────────────────────────────────────────────

interface StatsRowProps {
  cards: { title: string; value: string | number; prefix?: string; suffix?: string; color?: string }[]
}

function StatsRow({ cards }: StatsRowProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cards.length}, 1fr)`, gap: 12, marginBottom: 16 }}>
      {cards.map((c) => (
        <Card key={c.title} size="small" style={{ borderRadius: 10 }}>
          <Statistic
            title={c.title}
            value={c.value}
            prefix={c.prefix}
            suffix={c.suffix}
            valueStyle={{ fontSize: 18, color: c.color ?? '#1a1d23' }}
          />
        </Card>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface PortfolioTabProps {
  isActive: boolean
}

export default function PortfolioTab({ isActive }: PortfolioTabProps) {
  const portfolio = useUserStore((s) => s.profile.portfolio)
  const soldPositions = useUserStore((s) => s.profile.soldPositions ?? [])
  const removePosition = useUserStore((s) => s.removePosition)
  const removeSoldPosition = useUserStore((s) => s.removeSoldPosition)
  const fetchLivePrices = useUserStore((s) => s.fetchLivePrices)
  const fetchFxRates = useUserStore((s) => s.fetchFxRates)
  const livePrices = useUserStore((s) => s.livePrices)
  const fxRates = useUserStore((s) => s.fxRates)
  const fxLoading = useUserStore((s) => s.fxLoading)
  const pricesLoading = useUserStore((s) => s.pricesLoading)
  const pricesLastFetched = useUserStore((s) => s.pricesLastFetched)
  const loadFromServer = useUserStore((s) => s.loadFromServer)

  const [activeModal, setActiveModal] = useState(false)
  const [editActive, setEditActive] = useState<PortfolioPosition | null>(null)
  const [soldModal, setSoldModal] = useState(false)
  const [editSold, setEditSold] = useState<SoldPosition | null>(null)

  useEffect(() => { loadFromServer() }, [loadFromServer])

  useEffect(() => {
    if (isActive && portfolio.length > 0) {
      fetchLivePrices(portfolio.map((p) => p.ticker))
    }
  }, [isActive, portfolio.length, fetchLivePrices])

  useEffect(() => {
    const currencies = portfolio.map((p) => {
      const lp = livePrices[p.ticker]
      return lp?.currency ?? REGION_MAP[p.region ?? inferRegion(p.ticker)]?.currency ?? 'USD'
    }).filter((c) => c !== 'USD')
    if (currencies.length > 0) fetchFxRates(currencies)
  }, [livePrices, portfolio, fetchFxRates])

  const handleRefresh = () => {
    if (portfolio.length > 0) fetchLivePrices(portfolio.map((p) => p.ticker))
  }

  const toUSD = (amount: number, currency: string): number | null => {
    if (currency === 'USD') return amount
    const rate = fxRates[currency]
    if (rate == null) return null
    return amount * rate
  }

  const positionCurrency = (pos: PortfolioPosition): string => {
    const lp = livePrices[pos.ticker]
    return lp?.currency ?? REGION_MAP[pos.region ?? inferRegion(pos.ticker)]?.currency ?? 'USD'
  }

  const currencies = new Set(portfolio.map(positionCurrency))
  const isMultiCurrency = currencies.size > 1
  const allFxReady = [...currencies].every((c) => c === 'USD' || fxRates[c] != null)
  const totalsLoading = pricesLoading || fxLoading || !allFxReady

  // ── Active portfolio aggregate ──────────────────────────────────────────────
  const activeTotals = portfolio.reduce(
    (acc, pos) => {
      const lp = livePrices[pos.ticker]
      const ccy = positionCurrency(pos)
      const pnl = computePnL(pos, lp?.price ?? null, lp?.changePct ?? null, lp?.currency)
      const costUSD = toUSD(pnl.costBasis, ccy)
      const valueUSD = pnl.marketValue !== null ? toUSD(pnl.marketValue, ccy) : null
      const pnlUSD = pnl.unrealizedPnL !== null ? toUSD(pnl.unrealizedPnL, ccy) : null
      const dayUSD = pnl.dayChange !== null ? toUSD(pnl.dayChange, ccy) : null
      if (costUSD !== null) acc.totalCost += costUSD
      if (valueUSD !== null) acc.totalValue += valueUSD
      if (pnlUSD !== null) acc.totalPnL += pnlUSD
      if (dayUSD !== null) acc.totalDayChange += dayUSD
      return acc
    },
    { totalCost: 0, totalValue: 0, totalPnL: 0, totalDayChange: 0 }
  )
  const activePnLPct = activeTotals.totalCost > 0 ? (activeTotals.totalPnL / activeTotals.totalCost) * 100 : null

  // ── Sold positions aggregate (always in local currency → USD) ───────────────
  const soldTotals = soldPositions.reduce(
    (acc, pos) => {
      const ccy = REGION_MAP[pos.region ?? inferRegion(pos.ticker)]?.currency ?? 'USD'
      const cost = pos.shares * pos.avgCostBasis
      const proceeds = pos.shares * pos.soldPrice
      const realizedPnL = proceeds - cost
      const costUSD = toUSD(cost, ccy) ?? cost
      const proceedsUSD = toUSD(proceeds, ccy) ?? proceeds
      const pnlUSD = toUSD(realizedPnL, ccy) ?? realizedPnL
      acc.totalCost += costUSD
      acc.totalProceeds += proceedsUSD
      acc.totalPnL += pnlUSD
      acc.wins += realizedPnL >= 0 ? 1 : 0
      acc.losses += realizedPnL < 0 ? 1 : 0
      return acc
    },
    { totalCost: 0, totalProceeds: 0, totalPnL: 0, wins: 0, losses: 0 }
  )
  const soldPnLPct = soldTotals.totalCost > 0 ? (soldTotals.totalPnL / soldTotals.totalCost) * 100 : null

  // ── Global combined ─────────────────────────────────────────────────────────
  const combinedPnL = (totalsLoading ? 0 : activeTotals.totalPnL) + soldTotals.totalPnL
  const combinedCost = (totalsLoading ? 0 : activeTotals.totalCost) + soldTotals.totalCost
  const combinedPnLPct = combinedCost > 0 ? (combinedPnL / combinedCost) * 100 : null

  // ── Active portfolio columns ────────────────────────────────────────────────
  const activeColumns = [
    {
      title: 'Ticker', dataIndex: 'ticker', key: 'ticker', width: 120,
      render: (t: string, record: PortfolioPosition) => {
        const cfg = REGION_MAP[record.region ?? inferRegion(t)]
        return (
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 14 }}>{t}</Text>
            {cfg && <Text style={{ fontSize: 11, color: '#8a909e' }}>{cfg.flag} {cfg.label}</Text>}
          </Space>
        )
      },
    },
    {
      title: 'Shares', dataIndex: 'shares', key: 'shares', width: 80,
      render: (v: number) => <Text style={{ fontSize: 13 }}>{v.toLocaleString()}</Text>,
    },
    {
      title: 'Avg Cost', dataIndex: 'avgCostBasis', key: 'avgCostBasis', width: 110,
      render: (v: number, record: PortfolioPosition) => {
        const sym = currencySymbolForTicker(record.ticker)
        return <Text style={{ fontSize: 13 }}>{sym}{v.toLocaleString('en-US', { minimumFractionDigits: 2 })}</Text>
      },
    },
    {
      title: 'Current Price', key: 'currentPrice', width: 130,
      render: (_: unknown, record: PortfolioPosition) => {
        const lp = livePrices[record.ticker]
        if (!lp?.price) return <Text style={{ color: '#8a909e' }}>—</Text>
        const isUp = (lp.changePct ?? 0) >= 0
        const sym = currencySymbolForTicker(record.ticker, lp.currency)
        return (
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 13 }}>{sym}{lp.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</Text>
            <Text style={{ fontSize: 11, color: isUp ? '#16a34a' : '#dc2626' }}>
              {isUp ? '+' : ''}{lp.changePct?.toFixed(2)}% today
            </Text>
          </Space>
        )
      },
    },
    {
      title: 'Market Value', key: 'marketValue', width: 130,
      render: (_: unknown, record: PortfolioPosition) => {
        const lp = livePrices[record.ticker]
        const pnl = computePnL(record, lp?.price ?? null, lp?.changePct ?? null, lp?.currency)
        if (pnl.marketValue === null) return <Text style={{ color: '#8a909e' }}>—</Text>
        return <Text strong style={{ fontSize: 13 }}>{pnl.currencySym}{pnl.marketValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</Text>
      },
    },
    {
      title: 'Unrealized P&L', key: 'unrealizedPnL', width: 170,
      render: (_: unknown, record: PortfolioPosition) => {
        const lp = livePrices[record.ticker]
        const pnl = computePnL(record, lp?.price ?? null, lp?.changePct ?? null, lp?.currency)
        return <PnLText value={pnl.unrealizedPnL} pct={pnl.unrealizedPnLPct} sym={pnl.currencySym} />
      },
    },
    {
      title: "Today's Change", key: 'dayChange', width: 150,
      render: (_: unknown, record: PortfolioPosition) => {
        const lp = livePrices[record.ticker]
        const pnl = computePnL(record, lp?.price ?? null, lp?.changePct ?? null, lp?.currency)
        return <PnLText value={pnl.dayChange} pct={pnl.dayChangePct} sym={pnl.currencySym} />
      },
    },
    {
      title: 'Note', dataIndex: 'note', key: 'note',
      render: (note: string) =>
        note ? (
          <Tooltip title={note}>
            <Text style={{ fontSize: 12, color: '#4a5060', maxWidth: 160, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{note}</Text>
          </Tooltip>
        ) : <Text style={{ color: '#c4c8d0', fontSize: 12 }}>—</Text>,
    },
    {
      title: '', key: 'actions', width: 80,
      render: (_: unknown, record: PortfolioPosition) => (
        <Space size={4}>
          <Tooltip title="Edit">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => { setEditActive(record); setActiveModal(true) }} style={{ color: '#8a909e' }} />
          </Tooltip>
          <Popconfirm title={`Remove ${record.ticker}?`} onConfirm={() => { removePosition(record.ticker); message.success(`${record.ticker} removed`) }} okText="Remove" okButtonProps={{ danger: true }}>
            <Tooltip title="Remove">
              <Button type="text" size="small" icon={<DeleteOutlined />} style={{ color: '#dc2626' }} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // ── Sold positions columns ──────────────────────────────────────────────────
  const soldColumns = [
    {
      title: 'Ticker', dataIndex: 'ticker', key: 'ticker', width: 120,
      render: (t: string, record: SoldPosition) => {
        const cfg = REGION_MAP[record.region ?? inferRegion(t)]
        return (
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 14 }}>{t}</Text>
            {cfg && <Text style={{ fontSize: 11, color: '#8a909e' }}>{cfg.flag} {cfg.label}</Text>}
          </Space>
        )
      },
    },
    {
      title: 'Shares', dataIndex: 'shares', key: 'shares', width: 80,
      render: (v: number) => <Text style={{ fontSize: 13 }}>{v.toLocaleString()}</Text>,
    },
    {
      title: 'Avg Buy', dataIndex: 'avgCostBasis', key: 'avgCostBasis', width: 110,
      render: (v: number, record: SoldPosition) => {
        const sym = currencySymbolForTicker(record.ticker)
        return <Text style={{ fontSize: 13 }}>{sym}{v.toLocaleString('en-US', { minimumFractionDigits: 2 })}</Text>
      },
    },
    {
      title: 'Sell Price', dataIndex: 'soldPrice', key: 'soldPrice', width: 110,
      render: (v: number, record: SoldPosition) => {
        const sym = currencySymbolForTicker(record.ticker)
        return <Text style={{ fontSize: 13 }}>{sym}{v.toLocaleString('en-US', { minimumFractionDigits: 2 })}</Text>
      },
    },
    {
      title: 'Date Sold', dataIndex: 'soldAt', key: 'soldAt', width: 110,
      render: (v: string) => <Text style={{ fontSize: 12, color: '#4a5060' }}>{new Date(v).toLocaleDateString()}</Text>,
    },
    {
      title: 'Realized P&L', key: 'realizedPnL', width: 170,
      render: (_: unknown, record: SoldPosition) => {
        const sym = currencySymbolForTicker(record.ticker)
        const pnl = (record.soldPrice - record.avgCostBasis) * record.shares
        const pct = record.avgCostBasis !== 0 ? ((record.soldPrice - record.avgCostBasis) / record.avgCostBasis) * 100 : null
        return <PnLText value={pnl} pct={pct} sym={sym} />
      },
    },
    {
      title: 'Note', dataIndex: 'note', key: 'note',
      render: (note: string) =>
        note ? (
          <Tooltip title={note}>
            <Text style={{ fontSize: 12, color: '#4a5060', maxWidth: 160, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{note}</Text>
          </Tooltip>
        ) : <Text style={{ color: '#c4c8d0', fontSize: 12 }}>—</Text>,
    },
    {
      title: '', key: 'actions', width: 80,
      render: (_: unknown, record: SoldPosition) => (
        <Space size={4}>
          <Tooltip title="Edit">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => { setEditSold(record); setSoldModal(true) }} style={{ color: '#8a909e' }} />
          </Tooltip>
          <Popconfirm title={`Delete this ${record.ticker} sale record?`} onConfirm={() => { removeSoldPosition(record.id); message.success('Sale record deleted') }} okText="Delete" okButtonProps={{ danger: true }}>
            <Tooltip title="Delete">
              <Button type="text" size="small" icon={<DeleteOutlined />} style={{ color: '#dc2626' }} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const fmt = (v: number) => Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const sign = (v: number) => (v >= 0 ? '+$' : '-$')

  return (
    <div style={{ padding: '20px 24px', height: '100%', overflowY: 'auto' }}>

      {/* ── Global header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0, color: '#1a1d23' }}>
            <WalletOutlined style={{ marginRight: 8 }} />
            Portfolio
          </Title>
          <Text style={{ fontSize: 12, color: '#8a909e' }}>
            Track your holdings and P&L
            {pricesLastFetched && <> · Updated {new Date(pricesLastFetched).toLocaleTimeString()}</>}
          </Text>
        </div>
        <Button icon={pricesLoading ? <Spin size="small" /> : <ReloadOutlined />} onClick={handleRefresh} disabled={pricesLoading || portfolio.length === 0} size="small">
          Refresh Prices
        </Button>
      </div>

      {/* ── Global combined stats ── */}
      {(portfolio.length > 0 || soldPositions.length > 0) && (
        <div style={{ background: 'linear-gradient(135deg, #1a1d23 0%, #2d3142 100%)', borderRadius: 12, padding: '16px 20px', marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <TrophyOutlined style={{ color: '#f59e0b', fontSize: 16 }} />
            <Text style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 14 }}>Overall Performance (USD)</Text>
            <Text style={{ color: '#64748b', fontSize: 12 }}>— active unrealized + closed realized</Text>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            <div>
              <Text style={{ color: '#94a3b8', fontSize: 11, display: 'block' }}>Total Invested (USD)</Text>
              <Text style={{ color: '#f1f5f9', fontSize: 20, fontWeight: 700 }}>
                ${totalsLoading ? '…' : combinedCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Text>
            </div>
            <div>
              <Text style={{ color: '#94a3b8', fontSize: 11, display: 'block' }}>Combined P&L (USD)</Text>
              <Text style={{ color: totalsLoading ? '#94a3b8' : combinedPnL >= 0 ? '#4ade80' : '#f87171', fontSize: 20, fontWeight: 700 }}>
                {totalsLoading ? '…' : `${sign(combinedPnL)}${fmt(combinedPnL)}`}
              </Text>
            </div>
            <div>
              <Text style={{ color: '#94a3b8', fontSize: 11, display: 'block' }}>Combined Return</Text>
              <Text style={{ color: totalsLoading || combinedPnLPct === null ? '#94a3b8' : combinedPnL >= 0 ? '#4ade80' : '#f87171', fontSize: 20, fontWeight: 700 }}>
                {totalsLoading || combinedPnLPct === null ? '…' : `${combinedPnL >= 0 ? '+' : ''}${combinedPnLPct.toFixed(2)}%`}
              </Text>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 1 — Active Holdings
      ════════════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <WalletOutlined style={{ color: '#6366f1', fontSize: 16 }} />
          <Title level={5} style={{ margin: 0, color: '#1a1d23' }}>Active Holdings</Title>
          <Tag color="purple" style={{ borderRadius: 10 }}>{portfolio.length}</Tag>
        </div>
        <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => { setEditActive(null); setActiveModal(true) }}>
          Add Position
        </Button>
      </div>

      {portfolio.length > 0 && (
        <>
          {isMultiCurrency && (
            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: 12, color: '#1e40af', display: 'flex', alignItems: 'center', gap: 6 }}>
              <InfoCircleOutlined />
              Multi-currency portfolio — totals converted to USD using live FX rates.
              {!allFxReady && <Spin size="small" style={{ marginLeft: 6 }} />}
            </div>
          )}
          <StatsRow cards={[
            { title: 'Market Value (USD)', value: totalsLoading ? '—' : fmt(activeTotals.totalValue), prefix: totalsLoading ? '' : '$', color: '#1a1d23' },
            { title: 'Total Cost (USD)', value: totalsLoading ? '—' : fmt(activeTotals.totalCost), prefix: totalsLoading ? '' : '$', color: '#4a5060' },
            {
              title: 'Unrealized P&L (USD)',
              value: totalsLoading ? '—' : fmt(activeTotals.totalPnL),
              prefix: totalsLoading ? '' : sign(activeTotals.totalPnL),
              suffix: !totalsLoading && activePnLPct !== null ? `  (${activePnLPct >= 0 ? '+' : ''}${activePnLPct.toFixed(2)}%)` : '',
              color: totalsLoading ? '#8a909e' : activeTotals.totalPnL >= 0 ? '#16a34a' : '#dc2626',
            },
            {
              title: "Today's Change (USD)",
              value: totalsLoading ? '—' : fmt(activeTotals.totalDayChange),
              prefix: totalsLoading ? '' : sign(activeTotals.totalDayChange),
              color: totalsLoading ? '#8a909e' : activeTotals.totalDayChange >= 0 ? '#16a34a' : '#dc2626',
            },
          ]} />
        </>
      )}

      {portfolio.length === 0 ? (
        <Empty description="No active positions yet" style={{ marginTop: 40, marginBottom: 40 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditActive(null); setActiveModal(true) }}>Add your first position</Button>
        </Empty>
      ) : (
        <Table dataSource={portfolio} columns={activeColumns} rowKey="ticker" pagination={false} size="middle"
          style={{ background: '#fff', borderRadius: 10, marginBottom: 8 }} scroll={{ x: 1000 }} />
      )}

      <Divider style={{ margin: '28px 0' }} />

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 2 — Sold / Closed Positions
      ════════════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HistoryOutlined style={{ color: '#0ea5e9', fontSize: 16 }} />
          <Title level={5} style={{ margin: 0, color: '#1a1d23' }}>Sold / Closed Positions</Title>
          <Tag color="blue" style={{ borderRadius: 10 }}>{soldPositions.length}</Tag>
        </div>
        <Button icon={<PlusOutlined />} size="small" onClick={() => { setEditSold(null); setSoldModal(true) }}>
          Record Sale
        </Button>
      </div>

      {soldPositions.length > 0 && (
        <StatsRow cards={[
          { title: 'Total Proceeds (USD)', value: fmt(soldTotals.totalProceeds), prefix: '$', color: '#1a1d23' },
          { title: 'Total Cost Basis (USD)', value: fmt(soldTotals.totalCost), prefix: '$', color: '#4a5060' },
          {
            title: 'Realized P&L (USD)',
            value: fmt(soldTotals.totalPnL),
            prefix: sign(soldTotals.totalPnL),
            suffix: soldPnLPct !== null ? `  (${soldPnLPct >= 0 ? '+' : ''}${soldPnLPct.toFixed(2)}%)` : '',
            color: soldTotals.totalPnL >= 0 ? '#16a34a' : '#dc2626',
          },
          {
            title: 'Win / Loss',
            value: `${soldTotals.wins}W  ${soldTotals.losses}L`,
            color: soldTotals.wins >= soldTotals.losses ? '#16a34a' : '#dc2626',
          },
        ]} />
      )}

      {soldPositions.length === 0 ? (
        <Empty description="No sold positions recorded yet" style={{ marginTop: 40, marginBottom: 40 }}>
          <Button icon={<PlusOutlined />} onClick={() => { setEditSold(null); setSoldModal(true) }}>Record your first sale</Button>
        </Empty>
      ) : (
        <Table dataSource={soldPositions} columns={soldColumns} rowKey="id" pagination={false} size="middle"
          style={{ background: '#fff', borderRadius: 10 }} scroll={{ x: 1000 }} />
      )}

      {/* ── Modals ── */}
      <AddEditModal open={activeModal} initial={editActive} onClose={() => { setActiveModal(false); setEditActive(null) }} />
      <SoldModal open={soldModal} initial={editSold} onClose={() => { setSoldModal(false); setEditSold(null) }} />
    </div>
  )
}
