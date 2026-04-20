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

const RECOMMENDATION_COLOR: Record<string, string> = {
  BUY:        '#16a34a',
  ACCUMULATE: '#0f9960',
  HOLD:       '#b45309',
  TRIM:       '#c2410c',
  AVOID:      '#dc2626',
}

function RecommendationTag({ rec, score }: { rec?: string; score?: number }) {
  if (!rec) return null
  const color = RECOMMENDATION_COLOR[rec] ?? '#8a909e'
  return (
    <Tag
      style={{
        background: `${color}14`,
        color,
        borderColor: color,
        fontWeight: 700,
        fontSize: 12,
        letterSpacing: '0.05em',
      }}
    >
      {rec}
      {typeof score === 'number' && ` ${score >= 0 ? '+' : ''}${score.toFixed(1)}`}
    </Tag>
  )
}

function GapBar({ score }: { score?: number }) {
  if (typeof score !== 'number') return null
  const clamped = Math.max(-10, Math.min(10, score))
  const leftPct = ((clamped + 10) / 20) * 100
  const color = clamped > 2 ? '#16a34a' : clamped < -2 ? '#dc2626' : '#b45309'
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ position: 'relative', height: 10, background: '#f0f2f5', borderRadius: 5, border: '1px solid #e8eaed' }}>
        {/* center tick */}
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: '#dde1e7' }} />
        <div style={{ position: 'absolute', top: -4, bottom: -4, left: `${leftPct}%`, width: 4, background: color, borderRadius: 2, transform: 'translateX(-50%)', boxShadow: `0 0 6px ${color}` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#8a909e', fontFamily: 'monospace', marginTop: 2 }}>
        <span>-10 OVER</span><span>0</span><span>+10 UNDER</span>
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
  const layer = results.layer ?? {}
  const vcr = results.value_creation ?? {}
  const vcp = results.value_capture ?? {}
  const pg = results.pricing_gap ?? {}
  const ar = results.ai_risk ?? {}
  const syn = results.synthesis ?? {}

  const aiSkipped = !!(pg.skipped || vcr.skipped || vcp.skipped)
  const hasAiBlock = Object.keys(layer).length > 0 || Object.keys(syn).length > 0

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', borderBottom: '1px solid #e8eaed', background: '#f7f8fa', flexWrap: 'wrap' }}>
        <Title level={4} style={{ margin: 0, fontFamily: 'monospace', color: '#1a1d23' }}>{ticker}</Title>
        {fa.current_price && (
          <Text style={{ fontSize: 16, fontFamily: 'monospace', color: '#4a5060' }}>
            ${fa.current_price.toFixed(2)}
          </Text>
        )}
        {layer.primary_layer && (
          <Tag style={{ fontSize: 11, fontFamily: 'monospace', borderColor: '#4f6ef7', color: '#4f6ef7', background: '#4f6ef712' }}>
            {layer.primary_layer}
            {layer.primary_layer !== 'NEUTRAL' && layer.primary_layer_label ? ` · ${layer.primary_layer_label}` : ''}
          </Tag>
        )}
        <div style={{ flex: 1 }} />
        <RecommendationTag rec={syn.recommendation} score={syn.conviction_score} />
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

        {/* AI Value Chain */}
        {hasAiBlock && (
          <Col span={24} style={{ padding: '14px 16px', borderBottom: '1px solid #e8eaed', background: '#fafbfe' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Text style={{ fontSize: 11, color: '#4f6ef7', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                AI Value Chain
              </Text>
              {layer.ai_exposure_type && (
                <Tag style={{ fontSize: 10, margin: 0 }} color={layer.ai_exposure_type === 'DIRECT' ? 'blue' : layer.ai_exposure_type === 'INDIRECT' ? 'cyan' : 'default'}>
                  {layer.ai_exposure_type} · {layer.ai_exposure_score ?? 0}/100
                </Tag>
              )}
            </div>

            {aiSkipped ? (
              <Text style={{ fontSize: 12, color: '#8a909e', fontStyle: 'italic' }}>
                AI-specific analysis skipped — this company has NEUTRAL / MINIMAL AI exposure.
                Classic fundamental + growth signals remain authoritative.
              </Text>
            ) : (
              <>
                <Row gutter={[16, 12]}>
                  {/* Pricing Gap (headline signal) */}
                  <Col xs={24} md={12}>
                    <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Pricing Gap
                    </Text>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
                      <Text style={{ fontSize: 22, fontWeight: 700, fontFamily: 'monospace', color: (pg.gap_score ?? 0) > 2 ? '#16a34a' : (pg.gap_score ?? 0) < -2 ? '#dc2626' : '#b45309' }}>
                        {pg.gap_score != null ? `${pg.gap_score >= 0 ? '+' : ''}${pg.gap_score}` : '—'}
                      </Text>
                      <Text style={{ fontSize: 11, color: '#4a5060' }}>
                        {pg.gap_direction?.replace(/_/g, ' ')}
                        {pg.gap_magnitude ? ` · ${pg.gap_magnitude}` : ''}
                      </Text>
                    </div>
                    <GapBar score={pg.gap_score} />
                    <Row gutter={8} style={{ marginTop: 8 }}>
                      <Col span={12}>
                        <MetricCard label="Market implied growth" value={pg.market_implied_growth_rate_pct != null ? `${pg.market_implied_growth_rate_pct.toFixed(1)}%` : '—'} />
                      </Col>
                      <Col span={12}>
                        <MetricCard label="AI-scenario growth" value={pg.ai_scenario_growth_rate_pct != null ? `${pg.ai_scenario_growth_rate_pct.toFixed(1)}%` : '—'} color="#4f6ef7" />
                      </Col>
                      <Col span={12}>
                        <MetricCard label="Uncertainty" value={pg.uncertainty_driver ?? '—'} color={pg.uncertainty_driver === 'STRUCTURAL' ? '#16a34a' : pg.uncertainty_driver === 'SPECULATIVE' ? '#dc2626' : undefined} />
                      </Col>
                      <Col span={12}>
                        <MetricCard label="Horizon" value={pg.time_horizon ?? '—'} />
                      </Col>
                    </Row>
                    {pg.key_rerating_catalyst && (
                      <div style={{ marginTop: 8, fontSize: 12, color: '#4a5060', lineHeight: 1.45 }}>
                        <Text style={{ fontSize: 10, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', display: 'block' }}>Catalyst</Text>
                        {pg.key_rerating_catalyst}
                      </div>
                    )}
                  </Col>

                  {/* Creation / Capture scores */}
                  <Col xs={24} md={12}>
                    <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Value Creation / Capture
                    </Text>
                    <Row gutter={[12, 8]} style={{ marginTop: 4 }}>
                      <Col span={12}>
                        <MetricCard
                          label="Creation now → future"
                          value={`${vcr.current_creation_score ?? '—'} → ${vcr.future_creation_score ?? '—'}`}
                          color="#4f6ef7"
                        />
                        <Text style={{ fontSize: 10, color: '#8a909e' }}>
                          {vcr.current_creation_label} · ceiling {vcr.future_creation_ceiling?.replace(/_/g, ' ')}
                        </Text>
                      </Col>
                      <Col span={12}>
                        <MetricCard
                          label="Capture now → future"
                          value={`${vcp.current_capture_score ?? '—'} → ${vcp.future_capture_score ?? '—'}`}
                          color={vcp.future_capture_trajectory === 'EXPANDING' ? '#16a34a' : vcp.future_capture_trajectory === 'COMPRESSING' ? '#dc2626' : undefined}
                        />
                        <Text style={{ fontSize: 10, color: '#8a909e' }}>
                          {vcp.current_capture_rate} · {vcp.future_capture_trajectory?.toLowerCase()}
                        </Text>
                      </Col>
                      <Col span={12}>
                        <MetricCard label="AI role" value={vcr.ai_role?.replace(/_/g, ' ') ?? '—'} />
                      </Col>
                      <Col span={12}>
                        <MetricCard
                          label="Commoditization risk"
                          value={vcp.commoditization_risk ?? '—'}
                          color={vcp.commoditization_risk === 'HIGH' ? '#dc2626' : vcp.commoditization_risk === 'LOW' ? '#16a34a' : undefined}
                        />
                      </Col>
                    </Row>
                    {vcr.key_moat && (
                      <Text style={{ fontSize: 11, color: '#4a5060', display: 'block', marginTop: 6, fontStyle: 'italic' }}>
                        Moat: {vcr.key_moat}
                      </Text>
                    )}
                    {vcp.value_leakage_source && vcp.value_leakage_source.toLowerCase() !== 'none' && (
                      <Text style={{ fontSize: 11, color: '#4a5060', display: 'block', marginTop: 2 }}>
                        Leakage: {vcp.value_leakage_source}
                      </Text>
                    )}
                  </Col>
                </Row>

                {/* AI Risk */}
                {(ar.overall_risk_level || (ar.risks ?? []).length > 0) && (
                  <>
                    <Divider style={{ margin: '12px 0', borderColor: '#e8eaed' }} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        AI Risk
                      </Text>
                      {ar.overall_risk_level && (
                        <Tag color={ar.overall_risk_level === 'CRITICAL' ? 'red' : ar.overall_risk_level === 'HIGH' ? 'volcano' : ar.overall_risk_level === 'MODERATE' ? 'gold' : 'green'} style={{ fontSize: 10, margin: 0 }}>
                          {ar.overall_risk_level} · {ar.risk_score ?? 0}/100
                        </Tag>
                      )}
                    </div>
                    {ar.primary_risk && (
                      <Text style={{ fontSize: 12, color: '#4a5060', display: 'block', marginBottom: 6 }}>
                        <strong>Primary:</strong> {ar.primary_risk}
                      </Text>
                    )}
                    {(ar.risks ?? []).filter(r => r.severity === 'CRITICAL' || r.severity === 'HIGH').slice(0, 3).map((r, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#4a5060', marginBottom: 3, display: 'flex', gap: 6 }}>
                        <span style={{ width: 4, height: 4, borderRadius: '50%', background: r.severity === 'CRITICAL' ? '#dc2626' : '#c2410c', flexShrink: 0, marginTop: 6 }} />
                        <span>
                          <strong>{r.risk_type?.replace(/_/g, ' ')}</strong> ({r.severity}/{r.likelihood} · {r.timeline}) — {r.description}
                        </span>
                      </div>
                    ))}
                    {ar.thesis_breaker && (
                      <Text style={{ fontSize: 11, color: '#8a909e', display: 'block', marginTop: 6, fontStyle: 'italic' }}>
                        Thesis breaker: {ar.thesis_breaker}
                      </Text>
                    )}
                  </>
                )}

                {/* Synthesis thesis */}
                {syn.thesis && (
                  <>
                    <Divider style={{ margin: '12px 0', borderColor: '#e8eaed' }} />
                    <Text style={{ fontSize: 11, color: '#4f6ef7', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 4 }}>
                      Conviction Thesis
                    </Text>
                    <Text style={{ fontSize: 13, color: '#1a1d23', lineHeight: 1.5 }}>{syn.thesis}</Text>
                  </>
                )}
              </>
            )}
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
