import { useEffect, useRef } from 'react'
import { Empty, Typography, Progress, Space } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { usePipelineStore } from '../../store/pipelineStore'
import EventCard from './EventCard'

const { Text } = Typography

export default function LiveFeed() {
  const events = usePipelineStore((s) => s.events)
  const status = usePipelineStore((s) => s.status)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  // Compute pipeline stage progress from events
  const stageEvent = [...events].reverse().find((e) => e.type === 'pipeline_stage')
  const stageData = stageEvent?.data as { stage?: number; name?: string; total_stages?: number } | undefined

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {stageData && status === 'running' && (
        <div style={{ padding: '10px 20px', borderBottom: '1px solid #e8eaed', flexShrink: 0, background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <Text style={{ fontSize: 12, color: '#4a5060' }}>
              Stage {stageData.stage}/{stageData.total_stages}: {stageData.name}
            </Text>
            <Text style={{ fontSize: 11, color: '#8a909e' }}>
              {Math.round(((stageData.stage ?? 0) / (stageData.total_stages ?? 7)) * 100)}%
            </Text>
          </div>
          <Progress
            percent={Math.round(((stageData.stage ?? 0) / (stageData.total_stages ?? 7)) * 100)}
            showInfo={false}
            strokeColor="#4f6ef7"
            trailColor="#e8eaed"
            size="small"
          />
        </div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {events.length === 0 ? (
          <Empty
            image={<ThunderboltOutlined style={{ fontSize: 40, color: '#dde1e7' }} />}
            description={
              <Space direction="vertical" size={4} align="center">
                <Text style={{ color: '#4a5060', fontWeight: 600 }}>No events yet</Text>
                <Text style={{ fontSize: 12, color: '#8a909e' }}>
                  Run an analysis to see live agent activity
                </Text>
              </Space>
            }
            style={{ marginTop: 60 }}
          />
        ) : (
          events.map((evt, i) => (
            <div key={i} style={{ flexShrink: 0 }}>
              <EventCard event={evt} />
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
