import { useState } from 'react'
import { Layout, Tabs, Badge, Typography, Space, Segmented, Divider, Spin } from 'antd'
import {
  ThunderboltOutlined,
  BarChartOutlined,
  TrophyOutlined,
  FileTextOutlined,
  StockOutlined,
  SearchOutlined,
  EditOutlined,
  StarOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { usePipelineStore } from '../../store/pipelineStore'
import ManualRunForm from '../sidebar/ManualRunForm'
import DiscoverForm from '../sidebar/DiscoverForm'
import PastRunsList from '../sidebar/PastRunsList'
import PipelineProgress from '../sidebar/PipelineProgress'
import LiveFeed from '../feed/LiveFeed'
import ScreenTable from '../screen/ScreenTable'
import ResultsPanel from '../results/ResultsPanel'
import ReportViewer from '../report/ReportViewer'
import WatchlistTab from '../watchlist/WatchlistTab'
import PortfolioTab from '../portfolio/PortfolioTab'

const { Header, Sider, Content } = Layout
const { Text, Title } = Typography

type Mode = 'manual' | 'discover'

export default function AppShell() {
  const [mode, setMode] = useState<Mode>('manual')
  const activeTab = usePipelineStore((s) => s.activeTab)
  const setActiveTab = usePipelineStore((s) => s.setActiveTab)
  const events = usePipelineStore((s) => s.events)
  const screenResults = usePipelineStore((s) => s.screenResults)
  const allResults = usePipelineStore((s) => s.allResults)
  const status = usePipelineStore((s) => s.status)

  const feedCount = events.length
  const screenCount = screenResults.length
  const resultsCount = Object.keys(allResults).length

  const tabItems = [
    {
      key: 'watchlist',
      label: (
        <Space size={6}>
          <StarOutlined />
          Watchlist
        </Space>
      ),
      children: <WatchlistTab isActive={activeTab === 'watchlist'} />,
    },
    {
      key: 'portfolio',
      label: (
        <Space size={6}>
          <WalletOutlined />
          Portfolio
        </Space>
      ),
      children: <PortfolioTab isActive={activeTab === 'portfolio'} />,
    },
    {
      key: 'feed',
      label: (
        <Space size={6}>
          <ThunderboltOutlined />
          Live Feed
          <Badge count={feedCount} size="small" style={{ background: '#e8eaed', color: '#4a5060', boxShadow: 'none', fontSize: 10 }} />
        </Space>
      ),
      children: <LiveFeed />,
    },
    {
      key: 'screen',
      label: (
        <Space size={6}>
          <BarChartOutlined />
          Screen
          {screenCount > 0 && (
            <Badge count={screenCount} size="small" style={{ background: '#4f6ef712', color: '#4f6ef7', boxShadow: 'none', fontSize: 10 }} />
          )}
        </Space>
      ),
      children: <ScreenTable />,
    },
    {
      key: 'results',
      label: (
        <Space size={6}>
          <TrophyOutlined />
          Results
          {resultsCount > 0 && (
            <Badge count={resultsCount} size="small" style={{ background: '#16a34a12', color: '#16a34a', boxShadow: 'none', fontSize: 10 }} />
          )}
        </Space>
      ),
      children: <ResultsPanel />,
    },
    {
      key: 'report',
      label: (
        <Space size={6}>
          <FileTextOutlined />
          Report
        </Space>
      ),
      children: <ReportViewer />,
    },
  ]

  return (
    <Layout style={{ height: '100vh', background: '#f7f8fa' }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <Header
        style={{
          background: '#ffffff',
          borderBottom: '1px solid #dde1e7',
          boxShadow: '0 1px 4px rgba(0,0,0,.06)',
          padding: '0 24px',
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          flexShrink: 0,
        }}
      >
        <Space size={10}>
          <div style={{ width: 28, height: 28, background: '#4f6ef7', borderRadius: 6, display: 'grid', placeItems: 'center', fontSize: 14 }}>
            <StockOutlined style={{ color: '#fff' }} />
          </div>
          <Title level={5} style={{ margin: 0, color: '#1a1d23', fontWeight: 600 }}>
            Financial Analyst AI
          </Title>
        </Space>
        <Space size={12}>
          {status === 'running' && (
            <Space size={6}>
              <Spin size="small" />
              <Text style={{ fontSize: 12, color: '#4a5060' }}>Running pipeline…</Text>
            </Space>
          )}
          {status === 'complete' && (
            <Text style={{ fontSize: 12, color: '#16a34a' }}>Pipeline complete</Text>
          )}
          {status === 'error' && (
            <Text style={{ fontSize: 12, color: '#dc2626' }}>Pipeline error</Text>
          )}
          <Text style={{ fontSize: 12, color: '#8a909e' }}>
            {new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
          </Text>
        </Space>
      </Header>

      <Layout style={{ flex: 1, minHeight: 0, background: '#f7f8fa' }}>
        {/* ── Sidebar ─────────────────────────────────────────────── */}
        <Sider
          width={320}
          style={{
            background: '#ffffff',
            borderRight: '1px solid #dde1e7',
            overflowY: 'auto',
            padding: '16px 16px 24px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Segmented
            block
            value={mode}
            onChange={(v) => setMode(v as Mode)}
            options={[
              { value: 'manual', label: <Space size={4}><EditOutlined />Manual</Space> },
              { value: 'discover', label: <Space size={4}><SearchOutlined />Discover</Space> },
            ]}
            style={{ marginBottom: 16 }}
          />

          {mode === 'manual' ? <ManualRunForm /> : <DiscoverForm />}

          <Divider style={{ borderColor: '#e8eaed', margin: '20px 0 12px' }} />

          <PipelineProgress />

          <Divider style={{ borderColor: '#e8eaed', margin: '12px 0' }} />

          <Text style={{ fontSize: 11, color: '#8a909e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>
            Past Runs
          </Text>
          <PastRunsList />
        </Sider>

        {/* ── Main content ─────────────────────────────────────────── */}
        <Content style={{ display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', background: '#f7f8fa' }}>
          <Tabs
            activeKey={activeTab}
            onChange={(k) => setActiveTab(k as typeof activeTab)}
            items={tabItems}
            style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
            tabBarStyle={{ padding: '0 20px 0 16px', margin: 0, flexShrink: 0, background: '#ffffff', borderBottom: '1px solid #dde1e7' }}
          />
        </Content>
      </Layout>
    </Layout>
  )
}
