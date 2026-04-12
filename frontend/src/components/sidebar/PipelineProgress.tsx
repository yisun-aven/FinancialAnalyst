import { CheckCircleFilled, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import { usePipelineStore } from '../../store/pipelineStore'

const { Text } = Typography

const STAGES = [
  { key: 'Data Collection',      label: 'Data Collection' },
  { key: 'Fundamental Analysis', label: 'Fundamental Analysis' },
  { key: 'Growth Analysis',      label: 'Growth Analysis' },
  { key: 'Peer Comparison',      label: 'Peer Comparison' },
  { key: 'Technical Analysis',   label: 'Technical Analysis' },
  { key: 'Sentiment Analysis',   label: 'Sentiment Analysis' },
  { key: 'Report Writing',       label: 'Report Writing' },
]

export default function PipelineProgress() {
  const events = usePipelineStore((s) => s.events)
  const status = usePipelineStore((s) => s.status)

  if (status === 'idle') return null

  const stageEvents = events.filter((e) => e.type === 'pipeline_stage')
  const currentStageData = stageEvents.length > 0
    ? (stageEvents[stageEvents.length - 1].data as { stage: number; name: string; total_stages: number })
    : null

  const currentStageIdx = currentStageData ? currentStageData.stage - 1 : -1
  const isComplete = status === 'complete'
  const isError = status === 'error'

  return (
    <div style={{ marginBottom: 4 }}>
      <Text style={{
        fontSize: 11, color: '#8a909e', fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        display: 'block', marginBottom: 10,
      }}>
        Pipeline Progress
      </Text>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {STAGES.map((stage, idx) => {
          const isDone   = isComplete || idx < currentStageIdx
          const isActive = !isComplete && idx === currentStageIdx

          let icon: React.ReactNode
          let labelColor: string
          let rowBg: string

          if (isDone) {
            icon = <CheckCircleFilled style={{ color: '#16a34a', fontSize: 13 }} />
            labelColor = '#4a5060'
            rowBg = 'transparent'
          } else if (isActive) {
            icon = <LoadingOutlined style={{ color: '#4f6ef7', fontSize: 13 }} spin />
            labelColor = '#1a1d23'
            rowBg = '#4f6ef712'
          } else {
            icon = <ClockCircleOutlined style={{ color: '#dde1e7', fontSize: 13 }} />
            labelColor = '#8a909e'
            rowBg = 'transparent'
          }

          return (
            <div
              key={stage.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '5px 8px',
                borderRadius: 6,
                background: rowBg,
                transition: 'background 0.2s',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                {idx > 0 && (
                  <div style={{
                    width: 1,
                    height: 6,
                    background: idx <= currentStageIdx || isComplete ? '#16a34a' : '#dde1e7',
                    marginBottom: 2,
                    marginTop: -7,
                    marginLeft: 0,
                  }} />
                )}
                {icon}
              </div>
              <Text style={{ fontSize: 12, color: labelColor, fontWeight: isActive ? 600 : 400 }}>
                {stage.label}
              </Text>
              {isActive && (
                <Text style={{ fontSize: 10, color: '#4f6ef7', marginLeft: 'auto', fontFamily: 'monospace' }}>
                  running
                </Text>
              )}
              {isDone && !isComplete && (
                <Text style={{ fontSize: 10, color: '#16a34a', marginLeft: 'auto', fontFamily: 'monospace' }}>
                  done
                </Text>
              )}
            </div>
          )
        })}
      </div>

      {isError && (
        <Text style={{ fontSize: 11, color: '#dc2626', display: 'block', marginTop: 6 }}>
          Pipeline failed
        </Text>
      )}
    </div>
  )
}
