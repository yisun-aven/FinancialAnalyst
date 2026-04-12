import { useRef, useCallback } from 'react'
import type { WsEnvelope, PipelineCompleteData, ScreenResultsData } from '../types/events'
import { usePipelineStore } from '../store/pipelineStore'

function getWsUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  // In dev, Vite proxies /ws → backend. In prod, same host.
  return `${protocol}://${window.location.host}${path}`
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const { setStatus, setError, addEvent, setScreenResults, setPipelineComplete, setActiveTab } =
    usePipelineStore()

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const connect = useCallback(
    (path: string, payload: Record<string, unknown>) => {
      disconnect()
      usePipelineStore.getState().reset()
      setStatus('running')
      setActiveTab('feed')

      const ws = new WebSocket(getWsUrl(path))
      wsRef.current = ws

      ws.onopen = () => {
        ws.send(JSON.stringify(payload))
      }

      ws.onmessage = (evt) => {
        let msg: WsEnvelope
        try {
          msg = JSON.parse(evt.data as string) as WsEnvelope
        } catch {
          return
        }

        if (msg.type === 'ping') return

        addEvent(msg)

        if (msg.type === 'screen_results') {
          const data = msg.data as unknown as ScreenResultsData
          setScreenResults(data.stocks ?? [])
          setActiveTab('screen')
        }

        if (msg.type === 'pipeline_complete') {
          const data = msg.data as unknown as PipelineCompleteData
          setPipelineComplete(data)
          setActiveTab('results')
        }

        if (msg.type === 'pipeline_error') {
          const err = (msg.data as { error: string })?.error ?? 'Unknown error'
          setError(err)
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection error')
      }

      ws.onclose = (e) => {
        if (e.code !== 1000 && usePipelineStore.getState().status === 'running') {
          setError('Connection closed unexpectedly')
        }
      }
    },
    [disconnect, setStatus, setError, addEvent, setScreenResults, setPipelineComplete, setActiveTab],
  )

  return { connect, disconnect }
}
