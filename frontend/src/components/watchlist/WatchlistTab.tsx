import { useEffect, useState } from 'react'
import {
  Button, InputNumber, Select, Table, Tag, Typography, Space, Tooltip,
  Popconfirm, Form, Modal, Empty, Badge, Spin, message,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, BellOutlined,
  BellFilled, ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons'
import { useUserStore } from '../../store/userStore'
import type { WatchlistItem } from '../../types/user'
import TickerSearchSelect, { type TickerValue } from '../common/TickerSearchSelect'
import { inferRegion, currencySymbolForTicker, REGION_MAP } from '../../config/regions'

const { Text, Title } = Typography

const PRESET_TAGS = ['Buy', 'Hold', 'Avoid', 'Watch']

const TAG_COLORS: Record<string, string> = {
  Buy: 'green',
  Hold: 'blue',
  Avoid: 'red',
  Watch: 'orange',
}

function PriceCell({ ticker }: { ticker: string }) {
  const livePrices = useUserStore((s) => s.livePrices)
  const lp = livePrices[ticker]
  if (!lp) return <Text style={{ color: '#8a909e' }}>—</Text>
  if (lp.error || lp.price === null) return <Text style={{ color: '#dc2626', fontSize: 12 }}>N/A</Text>
  const isUp = (lp.changePct ?? 0) >= 0
  const sym = currencySymbolForTicker(ticker, lp.currency)
  return (
    <Space direction="vertical" size={0} style={{ whiteSpace: 'nowrap' }}>
      <Text strong style={{ fontSize: 14, whiteSpace: 'nowrap' }}>{sym}{lp.price?.toLocaleString()}</Text>
      <Space size={3} style={{ whiteSpace: 'nowrap' }}>
        {isUp ? <ArrowUpOutlined style={{ color: '#16a34a', fontSize: 10 }} /> : <ArrowDownOutlined style={{ color: '#dc2626', fontSize: 10 }} />}
        <Text style={{ fontSize: 11, color: isUp ? '#16a34a' : '#dc2626', whiteSpace: 'nowrap' }}>
          {isUp ? '+' : ''}{lp.changePct?.toFixed(2)}%
        </Text>
        <Text style={{ fontSize: 11, color: '#8a909e', whiteSpace: 'nowrap' }}>
          ({isUp ? '+' : ''}{sym}{lp.change?.toFixed(2)})
        </Text>
      </Space>
    </Space>
  )
}

function AlertCell({ item }: { item: WatchlistItem }) {
  const livePrices = useUserStore((s) => s.livePrices)
  const lp = livePrices[item.ticker]
  const sym = currencySymbolForTicker(item.ticker, lp?.currency)

  if (!item.alertPrice) {
    return <Text style={{ color: '#c4c8d0', fontSize: 12 }}>No alert</Text>
  }

  const currentPrice = lp?.price ?? null
  let triggered = false
  if (currentPrice !== null) {
    triggered =
      item.alertDirection === 'above'
        ? currentPrice >= item.alertPrice
        : currentPrice <= item.alertPrice
  }

  return (
    <Space size={4} style={{ whiteSpace: 'nowrap' }}>
      {triggered ? (
        <Badge dot color="#5F8575">
          <BellFilled style={{ color: '#5F8575', fontSize: 14 }} />
        </Badge>
      ) : (
        <BellOutlined style={{ color: '#8a909e', fontSize: 14 }} />
      )}
      <Text style={{ fontSize: 12, color: triggered ? '#5F8575' : '#4a5060', fontWeight: triggered ? 600 : 400, whiteSpace: 'nowrap' }}>
        {item.alertDirection === 'above' ? '≥' : '≤'} {sym}{item.alertPrice.toLocaleString()}
        {triggered && ' ⚡ Triggered'}
      </Text>
    </Space>
  )
}

interface AddEditModalProps {
  open: boolean
  initial?: WatchlistItem | null
  onClose: () => void
}

function AddEditModal({ open, initial, onClose }: AddEditModalProps) {
  const [form] = Form.useForm()
  const addToWatchlist = useUserStore((s) => s.addToWatchlist)
  const updateWatchlistItem = useUserStore((s) => s.updateWatchlistItem)

  const [tickerVal, setTickerVal] = useState<TickerValue>({
    region: initial?.region ?? 'US',
    ticker: initial?.ticker ?? '',
    name: '',
  })

  const regionCfg = REGION_MAP[tickerVal.region]
  const alertCurrencyLabel = regionCfg ? `Alert price (${regionCfg.currencySymbol})` : 'Alert price'

  useEffect(() => {
    if (open) {
      const initRegion = initial?.region ?? inferRegion(initial?.ticker ?? '')
      setTickerVal({ region: initRegion, ticker: initial?.ticker ?? '', name: '' })
      form.setFieldsValue(
        initial
          ? { alertPrice: initial.alertPrice, alertDirection: initial.alertDirection, tag: initial.tag, note: initial.note }
          : { alertPrice: null, alertDirection: 'below', tag: null, note: '' }
      )
    }
  }, [open, initial, form])

  const handleOk = () => {
    if (!tickerVal.ticker) {
      message.error('Please select a ticker')
      return
    }
    form.validateFields().then((vals) => {
      if (initial) {
        updateWatchlistItem(initial.ticker, {
          alertPrice: vals.alertPrice ?? null,
          alertDirection: vals.alertDirection,
          tag: vals.tag ?? null,
          note: vals.note ?? '',
        })
        message.success(`${initial.ticker} updated`)
      } else {
        addToWatchlist({
          ticker: tickerVal.ticker,
          region: tickerVal.region,
          alertPrice: vals.alertPrice ?? null,
          alertDirection: vals.alertDirection ?? 'below',
          tag: vals.tag ?? null,
          note: vals.note ?? '',
        })
        message.success(`${tickerVal.ticker} added to watchlist`)
      }
      onClose()
    })
  }

  return (
    <Modal
      title={initial ? `Edit ${initial.ticker}` : 'Add to Watchlist'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText={initial ? 'Save' : 'Add'}
      width={500}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="Region & Ticker" required>
          {initial ? (
            <Space>
              <Tag>{REGION_MAP[initial.region]?.flag} {REGION_MAP[initial.region]?.label}</Tag>
              <Text strong>{initial.ticker}</Text>
            </Space>
          ) : (
            <TickerSearchSelect
              value={tickerVal}
              onChange={(v) => setTickerVal(v)}
            />
          )}
          {tickerVal.name && (
            <Text style={{ fontSize: 12, color: '#8a909e', marginTop: 4, display: 'block' }}>
              {tickerVal.name}
            </Text>
          )}
        </Form.Item>

        <Space style={{ width: '100%' }} size={8}>
          <Form.Item name="alertDirection" label="Alert when price is" style={{ flex: 1, marginBottom: 0 }}>
            <Select style={{ width: 130 }}>
              <Select.Option value="below">Below ↓</Select.Option>
              <Select.Option value="above">Above ↑</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="alertPrice" label={alertCurrencyLabel} style={{ flex: 1, marginBottom: 0 }}>
            <InputNumber
              placeholder="e.g. 150.00"
              min={0}
              precision={2}
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Space>

        <Form.Item name="tag" label="Tag" style={{ marginTop: 16 }}>
          <Select
            placeholder="Select or type a tag"
            allowClear
            showSearch
            options={PRESET_TAGS.map((t) => ({ value: t, label: t }))}
          />
        </Form.Item>

        <Form.Item name="note" label="Note">
          <Form.Item name="note" noStyle>
            <textarea
              rows={3}
              placeholder="Your personal notes on this ticker…"
              style={{
                width: '100%',
                padding: '4px 11px',
                borderRadius: 6,
                border: '1px solid #dde1e7',
                fontSize: 14,
                fontFamily: 'inherit',
                resize: 'vertical',
                outline: 'none',
              }}
              onChange={(e) => form.setFieldValue('note', e.target.value)}
              defaultValue={initial?.note ?? ''}
            />
          </Form.Item>
        </Form.Item>
      </Form>
    </Modal>
  )
}

interface WatchlistTabProps {
  isActive: boolean
}

export default function WatchlistTab({ isActive }: WatchlistTabProps) {
  const watchlist = useUserStore((s) => s.profile.watchlist)
  const removeFromWatchlist = useUserStore((s) => s.removeFromWatchlist)
  const fetchLivePrices = useUserStore((s) => s.fetchLivePrices)
  const livePrices = useUserStore((s) => s.livePrices)
  const pricesLoading = useUserStore((s) => s.pricesLoading)
  const pricesLastFetched = useUserStore((s) => s.pricesLastFetched)
  const loadFromServer = useUserStore((s) => s.loadFromServer)

  const [modalOpen, setModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<WatchlistItem | null>(null)

  useEffect(() => {
    loadFromServer()
  }, [loadFromServer])

  // Refetch prices every time this tab becomes active
  useEffect(() => {
    if (isActive && watchlist.length > 0) {
      fetchLivePrices(watchlist.map((w) => w.ticker))
    }
  }, [isActive, watchlist.length, fetchLivePrices])

  const handleRefresh = () => {
    if (watchlist.length > 0) fetchLivePrices(watchlist.map((w) => w.ticker))
  }

  // Triggered alerts (computed from live prices)
  const triggeredAlerts = watchlist.filter((w) => {
    if (!w.alertPrice) return false
    const lp = livePrices[w.ticker]
    if (!lp?.price) return false
    return w.alertDirection === 'above' ? lp.price >= w.alertPrice : lp.price <= w.alertPrice
  })

  const columns = [
    {
      title: 'Ticker',
      dataIndex: 'ticker',
      key: 'ticker',
      width: 120,
      render: (t: string, record: WatchlistItem) => {
        const cfg = REGION_MAP[record.region ?? inferRegion(t)]
        return (
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 14, color: '#1a1d23' }}>{t}</Text>
            {cfg && (
              <Text style={{ fontSize: 11, color: '#8a909e' }}>{cfg.flag} {cfg.label}</Text>
            )}
          </Space>
        )
      },
    },
    {
      title: 'Price',
      key: 'price',
      width: 230,
      render: (_: unknown, record: WatchlistItem) => <PriceCell ticker={record.ticker} />,
    },
    {
      title: 'Alert',
      key: 'alert',
      width: 210,
      render: (_: unknown, record: WatchlistItem) => <AlertCell item={record} />,
    },
    {
      title: 'Tag',
      dataIndex: 'tag',
      key: 'tag',
      width: 90,
      render: (tag: string | null) =>
        tag ? (
          <Tag color={TAG_COLORS[tag] ?? 'default'} style={{ borderRadius: 4 }}>
            {tag}
          </Tag>
        ) : (
          <Text style={{ color: '#c4c8d0', fontSize: 12 }}>—</Text>
        ),
    },
    {
      title: 'Note',
      dataIndex: 'note',
      key: 'note',
      render: (note: string) =>
        note ? (
          <Tooltip title={note}>
            <Text style={{ fontSize: 12, color: '#4a5060', maxWidth: 200, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {note}
            </Text>
          </Tooltip>
        ) : (
          <Text style={{ color: '#c4c8d0', fontSize: 12 }}>—</Text>
        ),
    },
    {
      title: '',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: WatchlistItem) => (
        <Space size={4}>
          <Tooltip title="Edit">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => { setEditItem(record); setModalOpen(true) }} style={{ color: '#8a909e' }} />
          </Tooltip>
          <Popconfirm
            title={`Remove ${record.ticker} from watchlist?`}
            onConfirm={() => { removeFromWatchlist(record.ticker); message.success(`${record.ticker} removed`) }}
            okText="Remove"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="Remove">
              <Button type="text" size="small" icon={<DeleteOutlined />} style={{ color: '#dc2626' }} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '20px 24px', height: '100%', overflowY: 'auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0, color: '#1a1d23' }}>Watchlist</Title>
          <Text style={{ fontSize: 12, color: '#8a909e' }}>
            Track tickers and get price alerts
            {pricesLastFetched && <> · Updated {new Date(pricesLastFetched).toLocaleTimeString()}</>}
          </Text>
        </div>
        <Space>
          <Button
            icon={pricesLoading ? <Spin size="small" /> : <ReloadOutlined />}
            onClick={handleRefresh}
            disabled={pricesLoading || watchlist.length === 0}
            size="small"
          >
            Refresh Prices
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditItem(null); setModalOpen(true) }}>
            Add Ticker
          </Button>
        </Space>
      </div>

      {/* Triggered alerts banner */}
      {triggeredAlerts.length > 0 && (
        <div style={{ background: '#f0f5f2', border: '1px solid #b2ccc3', borderRadius: 8, padding: '10px 16px', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
          <BellFilled style={{ color: '#5F8575' }} />
          <Text style={{ color: '#3d6357', fontWeight: 500 }}>
            Price alert triggered:{' '}
            {triggeredAlerts.map((w) => {
              const lp = livePrices[w.ticker]
              const sym = currencySymbolForTicker(w.ticker, lp?.currency)
              return (
                <Tag key={w.ticker} color="#5F8575" style={{ marginLeft: 4 }}>
                  {w.ticker} {w.alertDirection === 'above' ? '≥' : '≤'} {sym}{w.alertPrice?.toLocaleString()}
                </Tag>
              )
            })}
          </Text>
        </div>
      )}

      {watchlist.length === 0 ? (
        <Empty description="No tickers in your watchlist yet" style={{ marginTop: 80 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditItem(null); setModalOpen(true) }}>
            Add your first ticker
          </Button>
        </Empty>
      ) : (
        <Table
          dataSource={watchlist}
          columns={columns}
          rowKey="ticker"
          pagination={false}
          size="middle"
          style={{ background: '#fff', borderRadius: 10 }}
          scroll={{ x: 'max-content' }}
          rowClassName={(record) => {
            const lp = livePrices[record.ticker]
            if (!record.alertPrice || !lp?.price) return ''
            const triggered = record.alertDirection === 'above' ? lp.price >= record.alertPrice : lp.price <= record.alertPrice
            return triggered ? 'alert-triggered-row' : ''
          }}
        />
      )}

      <AddEditModal
        open={modalOpen}
        initial={editItem}
        onClose={() => { setModalOpen(false); setEditItem(null) }}
      />

      <style>{`
        .alert-triggered-row td { background: #f0f5f2 !important; }
      `}</style>
    </div>
  )
}
