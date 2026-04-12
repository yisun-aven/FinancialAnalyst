import { Collapse, Typography, Tag, Space } from 'antd'
import {
  BarChartOutlined,
  RiseOutlined,
  TeamOutlined,
  LineChartOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import type { FundamentalResult, GrowthResult, PeerResult, TechnicalResult, SentimentResult } from '../../types/events'

const { Text, Paragraph } = Typography

interface Props {
  fundamental?: FundamentalResult
  growth?: GrowthResult
  peers?: PeerResult
  technical?: TechnicalResult
  sentiment?: SentimentResult
}

function ConfidenceBadge({ confidence }: { confidence?: string }) {
  if (!confidence) return null
  const colorMap: Record<string, string> = { high: 'green', medium: 'gold', low: 'red' }
  return <Tag color={colorMap[confidence] ?? 'default'} style={{ fontSize: 10 }}>{confidence}</Tag>
}

function ReasoningText({ text }: { text?: string }) {
  if (!text) return <Text style={{ color: '#8a909e', fontSize: 12 }}>No reasoning available.</Text>
  return (
    <Paragraph
      style={{
        fontSize: 13,
        color: '#4a5060',
        lineHeight: 1.6,
        borderLeft: '2px solid #dde1e7',
        paddingLeft: 10,
        fontStyle: 'italic',
        margin: 0,
      }}
    >
      {text}
    </Paragraph>
  )
}

export default function ReasoningAccordion({ fundamental, growth, peers, technical, sentiment }: Props) {
  const items = []

  if (fundamental) {
    items.push({
      key: 'fundamental',
      label: (
        <Space>
          <BarChartOutlined style={{ color: '#4f6ef7' }} />
          <Text strong style={{ fontSize: 13 }}>Fundamental Analyst</Text>
          <ConfidenceBadge confidence={fundamental.confidence} />
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <ReasoningText text={fundamental.reasoning} />
          {fundamental.entry_strategy && (
            <div style={{ padding: '8px 10px', background: '#4f6ef712', borderLeft: '3px solid #4f6ef7', borderRadius: '0 6px 6px 0', fontSize: 12, color: '#4a5060' }}>
              <Text strong style={{ color: '#4f6ef7', fontSize: 11 }}>Entry Strategy: </Text>
              {fundamental.entry_strategy}
            </div>
          )}
          {fundamental.target_price_rationale && (
            <Text style={{ fontSize: 12, color: '#4a5060' }}>
              <Text strong style={{ color: '#4a5060' }}>Target Rationale: </Text>
              {fundamental.target_price_rationale}
            </Text>
          )}
        </Space>
      ),
    })
  }

  if (growth) {
    items.push({
      key: 'growth',
      label: (
        <Space>
          <RiseOutlined style={{ color: '#16a34a' }} />
          <Text strong style={{ fontSize: 13 }}>Growth Analyst</Text>
          {growth.growth_quality_score !== undefined && (
            <Tag color="blue" style={{ fontFamily: 'monospace', fontSize: 10 }}>
              {growth.growth_quality_score}/10
            </Tag>
          )}
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <ReasoningText text={growth.reasoning} />
          {(growth.growth_risks ?? []).length > 0 && (
            <div>
              <Text style={{ fontSize: 11, color: '#dc2626', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Growth Risks
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                {growth.growth_risks!.map((r, i) => (
                  <Tag key={i} color="red" style={{ fontSize: 11 }}>{r}</Tag>
                ))}
              </div>
            </div>
          )}
        </Space>
      ),
    })
  }

  if (peers) {
    const disc = peers.composite_peer_discount_pct
    items.push({
      key: 'peers',
      label: (
        <Space>
          <TeamOutlined style={{ color: '#7c3aed' }} />
          <Text strong style={{ fontSize: 13 }}>Peer Comparison</Text>
          {disc != null && (
            <Tag color={disc > 0 ? 'green' : 'red'} style={{ fontSize: 10 }}>
              {disc > 0 ? '+' : ''}{disc.toFixed(1)}% vs peers
            </Tag>
          )}
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <ReasoningText text={peers.reasoning} />
          {peers.peer_comparison_note && (
            <Text style={{ fontSize: 11, color: '#8a909e' }}>{peers.peer_comparison_note}</Text>
          )}
        </Space>
      ),
    })
  }

  if (technical) {
    const tvColor: Record<string, string> = {
      strong_entry: '#16a34a',
      overbought: '#dc2626',
      avoid_entry: '#dc2626',
      neutral: '#b45309',
    }
    items.push({
      key: 'technical',
      label: (
        <Space>
          <LineChartOutlined style={{ color: '#b45309' }} />
          <Text strong style={{ fontSize: 13 }}>Technical Analyst</Text>
          {technical.entry_signal && (
            <Tag
              style={{
                fontSize: 10,
                background: `${tvColor[technical.entry_signal] ?? '#dde1e7'}18`,
                color: tvColor[technical.entry_signal] ?? '#4a5060',
                borderColor: tvColor[technical.entry_signal] ?? '#dde1e7',
              }}
            >
              {technical.entry_signal.replace(/_/g, ' ')}
            </Tag>
          )}
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <ReasoningText text={technical.reasoning} />
          {(technical.technical_risks ?? []).length > 0 && (
            <div>
              <Text style={{ fontSize: 11, color: '#dc2626', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Technical Risks
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                {technical.technical_risks!.map((r, i) => (
                  <Tag key={i} color="red" style={{ fontSize: 11 }}>{r}</Tag>
                ))}
              </div>
            </div>
          )}
        </Space>
      ),
    })
  }

  if (sentiment) {
    const sentColor: Record<string, string> = {
      very_bullish: '#16a34a', bullish: '#16a34a',
      neutral: '#b45309',
      bearish: '#dc2626', very_bearish: '#dc2626',
    }
    const label = sentiment.sentiment_label ?? ''
    items.push({
      key: 'sentiment',
      label: (
        <Space>
          <MessageOutlined style={{ color: '#c2410c' }} />
          <Text strong style={{ fontSize: 13 }}>Sentiment Analyst</Text>
          {label && (
            <Tag
              style={{
                fontSize: 10,
                background: `${sentColor[label] ?? '#dde1e7'}18`,
                color: sentColor[label] ?? '#4a5060',
                borderColor: sentColor[label] ?? '#dde1e7',
              }}
            >
              {label.replace(/_/g, ' ')}
            </Tag>
          )}
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <ReasoningText text={sentiment.reasoning} />
          {sentiment.insider_activity && (
            <Text style={{ fontSize: 12, color: '#4a5060' }}>
              <Text strong style={{ color: '#4a5060' }}>Insider: </Text>
              {sentiment.insider_activity}
            </Text>
          )}
          {(sentiment.top_headlines ?? []).length > 0 && (
            <div>
              <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Headlines
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                {sentiment.top_headlines!.slice(0, 5).map((h, i) => {
                  const dotColor = h.sentiment === 'positive' ? '#16a34a' : h.sentiment === 'negative' ? '#dc2626' : '#b45309'
                  return (
                    <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, flexShrink: 0, marginTop: 5 }} />
                      <Text style={{ color: '#4a5060', flex: 1, lineHeight: 1.4 }}>{h.title}</Text>
                      <Text style={{ fontSize: 10, color: '#8a909e', fontFamily: 'monospace', flexShrink: 0 }}>{h.date}</Text>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </Space>
      ),
    })
  }

  if (!items.length) return null

  return (
    <Collapse
      items={items}
      defaultActiveKey={['fundamental']}
      style={{ background: 'transparent', border: 'none' }}
      expandIconPosition="end"
    />
  )
}
