import { Card, Tag, Typography, Row, Col, Divider } from 'antd'
import type { AllResults } from '../../types/events'
import ReasoningAccordion from './ReasoningAccordion'

const { Text, Title } = Typography

interface Props {
  ticker: string
  results: AllResults
}

function fmt(v: number | null | undefined, decimals = 2, prefix = '') {
  if (v == null) return '—'
  return `${prefix}${v.toFixed(decimals)}`
}

function MetricCard({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Text style={{ fontSize: 11, color: '#8a909e' }}>{label}</Text>
      <Text style={{ fontSize: 14, fontWeight: 600, fontFamily: 'monospace', color: color ?? '#1a1d23' }}>
        {value}
      </Text>
    </div>
  )
}

function VerdictTag({ verdict }: { verdict?: string }) {
  if (!verdict) return null
  const map: Record<string, { color: string; bg: string }> = {
    undervalued:   { color: '#16a34a', bg: '#16a34a12' },
    fairly_valued: { color: '#b45309', bg: '#b4530912' },
    overvalued:    { color: '#dc2626', bg: '#dc262612' },
  }
  const style = map[verdict] ?? { color: '#8a909e', bg: '#f0f2f5' }
  return (
    <Tag style={{ background: style.bg, color: style.color, borderColor: style.color, fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {verdict.replace(/_/g, ' ')}
    </Tag>
  )
}

function TargetPriceGauge({ current, bear, base, bull }: { current?: number | null; bear?: number | null; base?: number | null; bull?: number | null }) {
  if (!current || !bear || !bull) return null
  const min = Math.min(current, bear) * 0.95
  const max = Math.max(current, bull) * 1.05
  const range = max - min
  const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / range) * 100)).toFixed(1)}%`

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ position: 'relative', height: 12, background: '#f0f2f5', borderRadius: 6, border: '1px solid #e8eaed', overflow: 'visible', margin: '6px 0 4px' }}>
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: pct(min), width: pct(bear), background: '#16a34a', opacity: 0.3, borderRadius: '6px 0 0 6px' }} />
        {base && <div style={{ position: 'absolute', top: 0, bottom: 0, left: pct(bear), width: `${((base - bear) / range) * 100}%`, background: '#b45309', opacity: 0.3 }} />}
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: pct(base ?? bear), right: 0, background: '#7c3aed', opacity: 0.3, borderRadius: '0 6px 6px 0' }} />
        <div style={{ position: 'absolute', top: -4, bottom: -4, left: pct(current), width: 4, background: '#4f6ef7', borderRadius: 2, transform: 'translateX(-50%)', zIndex: 3, boxShadow: '0 0 6px #4f6ef7' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'monospace', color: '#8a909e' }}>
        <span style={{ color: '#16a34a' }}>${bear?.toFixed(0)}</span>
        {base && <span style={{ color: '#b45309' }}>${base.toFixed(0)}</span>}
        <span style={{ color: '#7c3aed' }}>${bull?.toFixed(0)}</span>
      </div>
    </div>
  )
}

export default function TickerResultCard({ ticker, results }: Props) {
  const fa = results.fundamental ?? {}
  const ga = results.growth ?? {}
  const pa = results.peers ?? {}
  const ta = results.technical ?? {}
  const sa = results.sentiment ?? {}

  const sentColorMap: Record<string, string> = {
    very_bullish: '#16a34a', bullish: '#16a34a',
    neutral: '#b45309',
    bearish: '#dc2626', very_bearish: '#dc2626',
  }
  const sentColor = sentColorMap[sa.sentiment_label ?? ''] ?? '#8a909e'

  return (
    <Card
      style={{ marginBottom: 16, border: '1px solid #dde1e7', background: '#ffffff' }}
      styles={{ body: { padding: 0 } }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', borderBottom: '1px solid #e8eaed', background: '#f7f8fa' }}>
        <Title level={4} style={{ margin: 0, fontFamily: 'monospace', color: '#1a1d23' }}>{ticker}</Title>
        {fa.current_price && (
          <Text style={{ fontSize: 16, fontFamily: 'monospace', color: '#4a5060' }}>
            ${fa.current_price.toFixed(2)}
          </Text>
        )}
        <div style={{ flex: 1 }} />
        <VerdictTag verdict={fa.valuation_verdict} />
        {ga.growth_verdict && (
          <Tag color={ga.growth_verdict === 'strong_growth' ? 'green' : ga.growth_verdict === 'declining' ? 'red' : 'gold'} style={{ fontSize: 11 }}>
            {ga.growth_verdict.replace(/_/g, ' ')}
          </Tag>
        )}
      </div>

      {/* Metrics grid */}
      <Row gutter={0}>
        {/* Valuation */}
        <Col xs={24} sm={12} style={{ padding: '14px 16px', borderRight: '1px solid #e8eaed', borderBottom: '1px solid #e8eaed' }}>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
            Valuation
          </Text>
          <Row gutter={[12, 12]}>
            <Col span={12}><MetricCard label="P/E" value={fmt(fa.pe_ratio, 1)} /></Col>
            <Col span={12}><MetricCard label="EV/EBITDA" value={fmt(fa.ev_ebitda, 1)} /></Col>
            <Col span={12}><MetricCard label="DCF Value" value={fa.dcf_intrinsic_value ? `$${fa.dcf_intrinsic_value.toFixed(0)}` : '—'} color="#4f6ef7" /></Col>
            <Col span={12}>
              <MetricCard
                label="Margin of Safety"
                value={fa.dcf_margin_of_safety != null ? `${fa.dcf_margin_of_safety.toFixed(1)}%` : '—'}
                color={fa.dcf_margin_of_safety != null ? (fa.dcf_margin_of_safety > 0 ? '#16a34a' : '#dc2626') : undefined}
              />
            </Col>
            <Col span={12}><MetricCard label="PEG" value={fmt(fa.peg_ratio, 2)} /></Col>
            <Col span={12}><MetricCard label="P/FCF" value={fmt(fa.pfcf_ratio, 1)} /></Col>
          </Row>
          {(fa.target_price_bear || fa.target_price_bull) && (
            <>
              <Divider style={{ margin: '10px 0', borderColor: '#e8eaed' }} />
              <Text style={{ fontSize: 11, color: '#8a909e', display: 'block', marginBottom: 4 }}>Target Price Range</Text>
              <TargetPriceGauge
                current={fa.current_price}
                bear={fa.target_price_bear}
                base={fa.target_price_base}
                bull={fa.target_price_bull}
              />
            </>
          )}
        </Col>

        {/* Growth */}
        <Col xs={24} sm={12} style={{ padding: '14px 16px', borderBottom: '1px solid #e8eaed' }}>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
            Growth
          </Text>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <MetricCard
                label="Rev CAGR 3Y"
                value={ga.revenue_cagr_3y_pct != null ? `${ga.revenue_cagr_3y_pct.toFixed(1)}%` : '—'}
                color={ga.revenue_cagr_3y_pct != null ? (ga.revenue_cagr_3y_pct > 0 ? '#16a34a' : '#dc2626') : undefined}
              />
            </Col>
            <Col span={12}>
              <MetricCard
                label="EPS CAGR 3Y"
                value={ga.eps_cagr_3y_pct != null ? `${ga.eps_cagr_3y_pct.toFixed(1)}%` : '—'}
                color={ga.eps_cagr_3y_pct != null ? (ga.eps_cagr_3y_pct > 0 ? '#16a34a' : '#dc2626') : undefined}
              />
            </Col>
            <Col span={12}>
              <MetricCard
                label="FCF CAGR 3Y"
                value={ga.fcf_cagr_3y_pct != null ? `${ga.fcf_cagr_3y_pct.toFixed(1)}%` : '—'}
                color={ga.fcf_cagr_3y_pct != null ? (ga.fcf_cagr_3y_pct > 0 ? '#16a34a' : '#dc2626') : undefined}
              />
            </Col>
            <Col span={12}>
              <MetricCard label="Quality Score" value={ga.growth_quality_score != null ? `${ga.growth_quality_score}/10` : '—'} color="#4f6ef7" />
            </Col>
          </Row>
          {(ga.growth_catalysts ?? []).length > 0 && (
            <>
              <Divider style={{ margin: '10px 0', borderColor: '#e8eaed' }} />
              <Text style={{ fontSize: 11, color: '#16a34a', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>
                Catalysts
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {ga.growth_catalysts!.slice(0, 3).map((c, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, fontSize: 12, color: '#4a5060' }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#16a34a', flexShrink: 0, marginTop: 6 }} />
                    {c}
                  </div>
                ))}
              </div>
            </>
          )}
        </Col>

        {/* Peers */}
        <Col xs={24} sm={12} style={{ padding: '14px 16px', borderRight: '1px solid #e8eaed', borderBottom: '1px solid #e8eaed' }}>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
            Peer Comparison
          </Text>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <MetricCard
                label="PE Discount vs Peers"
                value={pa.company_pe_discount_pct != null ? `${pa.company_pe_discount_pct > 0 ? '+' : ''}${pa.company_pe_discount_pct.toFixed(1)}%` : '—'}
                color={pa.company_pe_discount_pct != null ? (pa.company_pe_discount_pct > 0 ? '#16a34a' : '#dc2626') : undefined}
              />
            </Col>
            <Col span={12}><MetricCard label="Sector Median PE" value={fmt(pa.sector_median_pe, 1)} /></Col>
            <Col span={24}>
              <Text style={{ fontSize: 11, color: '#8a909e' }}>Sector: </Text>
              <Text style={{ fontSize: 12, color: '#4a5060' }}>{pa.sector ?? '—'}</Text>
            </Col>
          </Row>
          {(pa.peers_used ?? []).length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {pa.peers_used!.map((p) => (
                <Tag key={p} style={{ fontSize: 10, padding: '0 4px', margin: 0 }}>{p}</Tag>
              ))}
            </div>
          )}
        </Col>

        {/* Technical + Sentiment */}
        <Col xs={24} sm={12} style={{ padding: '14px 16px', borderBottom: '1px solid #e8eaed' }}>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
            Technical
          </Text>
          <Row gutter={[12, 12]}>
            <Col span={12}><MetricCard label="RSI 14" value={fmt(ta.rsi_14, 1)} color={ta.rsi_14 != null ? (ta.rsi_14 > 70 ? '#dc2626' : ta.rsi_14 < 30 ? '#16a34a' : '#4a5060') : undefined} /></Col>
            <Col span={12}><MetricCard label="52W Position" value={ta.position_52w != null ? `${ta.position_52w.toFixed(0)}%` : '—'} /></Col>
            <Col span={12}><MetricCard label="MA Cross" value={ta.cross_signal?.replace(/_/g, ' ') ?? '—'} color={ta.cross_signal === 'golden_cross' ? '#16a34a' : ta.cross_signal === 'death_cross' ? '#dc2626' : undefined} /></Col>
            <Col span={12}><MetricCard label="Vol Ratio" value={fmt(ta.volume_ratio, 2)} /></Col>
          </Row>
          <Divider style={{ margin: '10px 0', borderColor: '#e8eaed' }} />
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Sentiment
          </Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text style={{ fontSize: 28, fontWeight: 700, fontFamily: 'monospace', color: sentColor }}>
              {sa.sentiment_score != null ? sa.sentiment_score.toFixed(1) : '—'}
            </Text>
            <div>
              {sa.sentiment_label && (
                <Tag style={{ background: `${sentColor}14`, color: sentColor, borderColor: sentColor, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>
                  {sa.sentiment_label.replace(/_/g, ' ')}
                </Tag>
              )}
              {sa.analyst_consensus && (
                <Text style={{ display: 'block', fontSize: 11, color: '#8a909e', marginTop: 2 }}>{sa.analyst_consensus}</Text>
              )}
            </div>
          </div>
        </Col>

        {/* Risks & Strengths */}
        {((fa.key_risks ?? []).length > 0 || (fa.key_strengths ?? []).length > 0) && (
          <Col span={24} style={{ padding: '14px 16px', borderBottom: '1px solid #e8eaed' }}>
            <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
              Risks &amp; Strengths
            </Text>
            <Row gutter={16}>
              <Col xs={24} sm={12}>
                <Text style={{ fontSize: 11, color: '#dc2626', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>Risks</Text>
                {(fa.key_risks ?? []).map((r, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, fontSize: 12, color: '#4a5060', marginBottom: 3, lineHeight: 1.4 }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#dc2626', flexShrink: 0, marginTop: 6 }} />
                    {r}
                  </div>
                ))}
              </Col>
              <Col xs={24} sm={12}>
                <Text style={{ fontSize: 11, color: '#16a34a', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>Strengths</Text>
                {(fa.key_strengths ?? []).map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, fontSize: 12, color: '#4a5060', marginBottom: 3, lineHeight: 1.4 }}>
                    <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#16a34a', flexShrink: 0, marginTop: 6 }} />
                    {s}
                  </div>
                ))}
              </Col>
            </Row>
          </Col>
        )}

        {/* Agent Reasoning Accordion */}
        <Col span={24} style={{ padding: '14px 16px' }}>
          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 10 }}>
            Agent Reasoning
          </Text>
          <ReasoningAccordion
            fundamental={results.fundamental}
            growth={results.growth}
            peers={results.peers}
            technical={results.technical}
            sentiment={results.sentiment}
          />
        </Col>
      </Row>
    </Card>
  )
}
