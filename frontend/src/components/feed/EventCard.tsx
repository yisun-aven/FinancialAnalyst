import { useState } from 'react'
import { Tag, Typography } from 'antd'
import {
  ThunderboltOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  FileTextOutlined,
  BarChartOutlined,
  ClockCircleOutlined,
  CaretDownOutlined,
  CaretUpOutlined,
} from '@ant-design/icons'
import type { WsEnvelope } from '../../types/events'

const { Text } = Typography

interface Props {
  event: WsEnvelope
}

const EVENT_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pipeline_stage:        { label: 'Stage',      color: '#7c3aed', icon: <ThunderboltOutlined /> },
  agent_start:           { label: 'Agent',      color: '#4f6ef7', icon: <RobotOutlined /> },
  agent_complete:        { label: 'Done',       color: '#16a34a', icon: <CheckCircleOutlined /> },
  agent_ticker_start:    { label: 'Ticker',     color: '#8a909e', icon: <SyncOutlined spin /> },
  agent_ticker_complete: { label: 'Ticker ✓',  color: '#4f6ef7', icon: <CheckCircleOutlined /> },
  claude_call_start:     { label: 'Claude',     color: '#c2410c', icon: <RobotOutlined /> },
  claude_call_complete:  { label: 'Claude ✓',  color: '#b45309', icon: <CheckCircleOutlined /> },
  rate_limit_wait:       { label: 'Rate Limit', color: '#dc2626', icon: <ClockCircleOutlined /> },
  report_ready:          { label: 'Report',     color: '#16a34a', icon: <FileTextOutlined /> },
  pipeline_complete:     { label: 'Complete',   color: '#16a34a', icon: <CheckCircleOutlined /> },
  pipeline_error:        { label: 'Error',      color: '#dc2626', icon: <WarningOutlined /> },
  universe_loaded:       { label: 'Universe',   color: '#7c3aed', icon: <BarChartOutlined /> },
  screener_start:        { label: 'Screen',     color: '#4f6ef7', icon: <BarChartOutlined /> },
  screener_progress:     { label: 'Progress',   color: '#8a909e', icon: <SyncOutlined spin /> },
  screener_complete:     { label: 'Screened',   color: '#16a34a', icon: <CheckCircleOutlined /> },
  screen_results:        { label: 'Results',    color: '#16a34a', icon: <BarChartOutlined /> },
}

function formatTime(ts?: string) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function hasDetails(event: WsEnvelope) {
  return event.data && Object.keys(event.data).length > 0
}

export default function EventCard({ event }: Props) {
  const [open, setOpen] = useState(false)
  const meta = EVENT_META[event.type] ?? { label: event.type, color: '#8a909e', icon: <ThunderboltOutlined /> }

  const borderColor = meta.color
  const isError = event.type === 'pipeline_error'
  const isComplete = event.type === 'pipeline_complete' || event.type === 'report_ready'

  return (
    <div
      style={{
        border: `1px solid #e8eaed`,
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 8,
        background: isError ? '#dc262608' : isComplete ? '#16a34a08' : '#ffffff',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          cursor: hasDetails(event) ? 'pointer' : 'default',
          userSelect: 'none',
        }}
        onClick={() => hasDetails(event) && setOpen((o) => !o)}
      >
        <Tag
          style={{ margin: 0, fontSize: 10, padding: '0 6px', borderColor: borderColor, color: borderColor, background: `${borderColor}14` }}
        >
          {meta.label}
        </Tag>

        {event.agent && (
          <Tag style={{ margin: 0, fontSize: 10, padding: '0 6px', background: '#f0f2f5', color: '#4a5060', border: '1px solid #dde1e7' }}>
            {event.agent}
          </Tag>
        )}

        {event.ticker && (
          <Tag color="blue" style={{ margin: 0, fontSize: 10, padding: '0 6px' }}>
            {event.ticker}
          </Tag>
        )}

        <Text style={{ flex: 1, fontSize: 12, color: '#1a1d23' }} ellipsis>
          {event.message ?? event.type}
        </Text>

        <Text style={{ fontSize: 10, color: '#8a909e', fontFamily: 'monospace', flexShrink: 0 }}>
          {formatTime(event.timestamp)}
        </Text>

        {hasDetails(event) && (
          <span style={{ color: '#8a909e', fontSize: 10 }}>
            {open ? <CaretUpOutlined /> : <CaretDownOutlined />}
          </span>
        )}
      </div>

      {open && hasDetails(event) && (
        <div
          style={{
            padding: '8px 12px 10px',
            borderTop: '1px solid #e8eaed',
            background: '#f7f8fa',
            fontSize: 12,
            fontFamily: 'monospace',
            color: '#4a5060',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxHeight: 300,
            overflowY: 'auto',
          }}
        >
          {JSON.stringify(event.data, null, 2)}
        </div>
      )}
    </div>
  )
}
