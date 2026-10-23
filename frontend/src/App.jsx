import { useState, useEffect } from 'react'
import axios from 'axios'

function App() {
  const [apiStatus, setApiStatus] = useState('checking...')

  useEffect(() => {
    // 检查后端连接
    axios.get('/api/v1/health')
      .then(res => {
        setApiStatus(`✅ 已连接 - ${res.data.service} v${res.data.version}`)
      })
      .catch(err => {
        setApiStatus(`❌ Connection failed: ${err.message}`)
      })
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-2xl w-full">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            AI Insight Hub
          </h1>
          <p className="text-lg text-gray-600 mb-8">
            AI 驱动的智能对话数据分析平台
          </p>

          <div className="bg-gray-50 rounded-lg p-6 mb-8">
            <p className="text-sm text-gray-500 mb-2">后端 API 状态</p>
            <p className="text-lg font-mono">{apiStatus}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="text-3xl mb-2">🔧</div>
              <h3 className="font-semibold text-gray-900">数据清洗</h3>
              <p className="text-sm text-gray-600">智能标准化处理</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <div className="text-3xl mb-2">🤖</div>
              <h3 className="font-semibold text-gray-900">AI 评估</h3>
              <p className="text-sm text-gray-600">质量自动分析</p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <div className="text-3xl mb-2">📚</div>
              <h3 className="font-semibold text-gray-900">知识构建</h3>
              <p className="text-sm text-gray-600">FAQ 自动提取</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <div className="text-3xl mb-2">📊</div>
              <h3 className="font-semibold text-gray-900">洞察报告</h3>
              <p className="text-sm text-gray-600">数据深度分析</p>
            </div>
          </div>

          <div className="text-sm text-gray-500">
            <p>🚧 项目开发中...</p>
            <p className="mt-2">当前阶段：需求收集 & 架构设计</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
