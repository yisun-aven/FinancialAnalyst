import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#4f6ef7',
          colorBgBase: '#f7f8fa',
          colorBgContainer: '#ffffff',
          colorBgElevated: '#ffffff',
          colorBorder: '#dde1e7',
          colorBorderSecondary: '#e8eaed',
          colorText: '#1a1d23',
          colorTextSecondary: '#4a5060',
          colorTextTertiary: '#8a909e',
          colorSuccess: '#16a34a',
          colorError: '#dc2626',
          colorWarning: '#b45309',
          borderRadius: 8,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
        },
        components: {
          Layout: {
            headerBg: '#ffffff',
            siderBg: '#ffffff',
            bodyBg: '#f7f8fa',
          },
          Tabs: {
            inkBarColor: '#4f6ef7',
            itemActiveColor: '#1a1d23',
            itemSelectedColor: '#1a1d23',
            itemHoverColor: '#4a5060',
          },
          Segmented: {
            trackBg: '#f0f2f5',
            itemSelectedBg: '#ffffff',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
