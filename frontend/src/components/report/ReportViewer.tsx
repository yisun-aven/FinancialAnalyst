import { useCallback, useEffect, useRef, useState } from 'react'
import { Empty, Spin, Select, Typography, Button, Alert, message } from 'antd'
import { FileTextOutlined, ReloadOutlined, DownloadOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../../api/rest'
import { usePipelineStore } from '../../store/pipelineStore'
import type { ReportSummary } from '../../types/api'

const { Text } = Typography

const mdStyles = `
  .report-md { font-size: 14px; line-height: 1.7; color: #1a1d23; max-width: 860px; margin: 0 auto; }
  .report-md h1 { font-size: 22px; margin-bottom: 8px; color: #1a1d23; }
  .report-md h2 { font-size: 17px; margin: 24px 0 10px; border-bottom: 1px solid #e8eaed; padding-bottom: 6px; color: #1a1d23; }
  .report-md h3, .report-md h4 { font-size: 14px; margin: 16px 0 8px; color: #4a5060; }
  .report-md p { margin-bottom: 10px; color: #4a5060; }
  .report-md strong { color: #1a1d23; }
  .report-md ul, .report-md ol { padding-left: 20px; margin-bottom: 10px; color: #4a5060; }
  .report-md li { margin-bottom: 4px; }
  .report-md table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  .report-md th { background: #f0f2f5; padding: 8px 12px; text-align: left; border: 1px solid #dde1e7; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #8a909e; }
  .report-md td { padding: 8px 12px; border: 1px solid #e8eaed; color: #4a5060; }
  .report-md tr:hover td { background: #f7f8fa; }
  .report-md blockquote { border-left: 3px solid #b45309; padding: 8px 14px; background: #b4530912; border-radius: 0 6px 6px 0; margin: 10px 0; }
  .report-md code { font-family: monospace; font-size: 12px; background: #f0f2f5; padding: 2px 6px; border-radius: 4px; color: #7c3aed; }
  .report-md pre { background: #f0f2f5; border: 1px solid #e8eaed; border-radius: 8px; padding: 14px; overflow-x: auto; }
  .report-md pre code { background: none; padding: 0; }
  .report-md hr { border: none; border-top: 1px solid #e8eaed; margin: 20px 0; }
  .report-md em { color: #8a909e; }
  .report-md a { color: #4f6ef7; }
`

export default function ReportViewer() {
  const storeFilename = usePipelineStore((s) => s.reportFilename)
  const storeContent  = usePipelineStore((s) => s.reportContent)
  const setReportContent = usePipelineStore((s) => s.setReportContent)

  const [reports, setReports]     = useState<ReportSummary[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent]     = useState<string | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const lastFetched = useRef<string | null>(null)

  const fetchReport = useCallback(async (filename: string) => {
    if (!filename) return
    lastFetched.current = filename
    setSelectedFile(filename)
    setLoading(true)
    setError(null)
    setContent(null)
    try {
      const d = await api.getReport(filename)
      setContent(d.content)
      setReportContent(d.content)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load report')
    } finally {
      setLoading(false)
    }
  }, [setReportContent])

  const refreshList = useCallback(() => {
    api.getReports().then(setReports).catch(() => {})
  }, [])

  const downloadPdf = useCallback(async (filename: string) => {
    if (!filename) return
    setDownloading(true)
    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(filename)}/pdf`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        throw new Error(body.error ?? `HTTP ${res.status}`)
      }
      const blob = await res.blob()
      const pdfName = filename.replace(/\.md$/, '') + '.pdf'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = pdfName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      message.success(`Downloaded ${pdfName}`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'PDF download failed')
    } finally {
      setDownloading(false)
    }
  }, [])

  useEffect(() => { refreshList() }, [refreshList])

  useEffect(() => {
    if (!storeFilename) return
    setSelectedFile(storeFilename)
    refreshList()

    if (storeContent != null) {
      setContent(storeContent)
      setError(null)
      lastFetched.current = storeFilename
    } else if (lastFetched.current !== storeFilename) {
      fetchReport(storeFilename)
    }
  }, [storeFilename, storeContent, fetchReport, refreshList])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <style>{mdStyles}</style>

      {/* Toolbar */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid #dde1e7', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, background: '#ffffff' }}>
        <FileTextOutlined style={{ color: '#4f6ef7' }} />
        <Text style={{ fontSize: 12, color: '#4a5060' }}>Report:</Text>
        <Select
          style={{ flex: 1, maxWidth: 500 }}
          placeholder="Select a report…"
          value={selectedFile}
          onChange={fetchReport}
          options={[
            ...(selectedFile && !reports.find((r) => r.filename === selectedFile)
              ? [{ value: selectedFile, label: selectedFile }]
              : []),
            ...reports.map((r) => ({ value: r.filename, label: r.filename })),
          ]}
          size="small"
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => {
            refreshList()
            if (selectedFile) fetchReport(selectedFile)
          }}
        >
          Refresh
        </Button>
        <Button
          size="small"
          type="primary"
          icon={<DownloadOutlined />}
          loading={downloading}
          disabled={!selectedFile || loading || !!error}
          onClick={() => selectedFile && downloadPdf(selectedFile)}
        >
          PDF
        </Button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px 32px', background: '#f7f8fa' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 60 }}>
            <Spin size="large" />
          </div>
        ) : error ? (
          <Alert
            type="error"
            message="Failed to load report"
            description={error}
            showIcon
            style={{ maxWidth: 600, margin: '60px auto 0' }}
          />
        ) : content != null ? (
          <div className="report-md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Text style={{ color: '#8a909e' }}>
                No report loaded — run an analysis or select a past report
              </Text>
            }
            style={{ marginTop: 60 }}
          />
        )}
      </div>
    </div>
  )
}
