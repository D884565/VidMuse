import { useState, useEffect } from 'react'
import Modal from '@/components/Modal/Modal'
import Tabs from '@/components/Tabs/Tabs'
import Badge from '@/components/Badge/Badge'
import PipelineProgress from './PipelineProgress'
import PipelineFlowChart from './PipelineFlowChart'
import { getPipelineDetail } from '@/services/admin'

const getStatusBadge = (status) => {
  const statusMap = {
    pending: { label: '待执行', color: 'gray' },
    running: { label: '执行中', color: 'blue' },
    completed: { label: '已完成', color: 'green' },
    failed: { label: '失败', color: 'red' },
    cancelled: { label: '已取消', color: 'yellow' }
  }
  const config = statusMap[status] || { label: status, color: 'gray' }
  return <Badge color={config.color}>{config.label}</Badge>
}

const JsonViewer = ({ data }) => {
  if (!data) return <span className="text-gray-400">无数据</span>
  return (
    <pre className="bg-gray-50 p-3 rounded-md text-xs overflow-x-auto max-h-60">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export default function PipelineDetailModal({ visible, executionId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('basic')

  useEffect(() => {
    if (visible && executionId) {
      loadDetail()
    }
  }, [visible, executionId])

  const loadDetail = async () => {
    try {
      setLoading(true)
      const res = await getPipelineDetail(executionId)
      setDetail(res.data)
    } catch (error) {
      console.error('加载详情失败:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!visible) return null

  const tabItems = [
    { key: 'basic', label: '基础信息' },
    { key: 'flow', label: '执行流程' },
    { key: 'params', label: '参数' },
    { key: 'context', label: '上下文' },
    { key: 'result', label: '执行结果' },
    { key: 'errors', label: '错误信息' }
  ]

  // 模拟处理器列表（实际应从detail中获取，此处为示例）
  const processors = detail?.context_metadata?.processors || [
    { name: '参数校验' },
    { name: '数据准备' },
    { name: '核心处理' },
    { name: '结果保存' },
    { name: '通知推送' }
  ]

  return (
    <Modal
      visible={visible}
      title="流水线执行详情"
      width={800}
      onCancel={onClose}
      footer={null}
    >
      {loading ? (
        <div className="flex justify-center py-8">加载中...</div>
      ) : !detail ? (
        <div className="text-center py-8 text-gray-500">加载失败</div>
      ) : (
        <div>
          {/* 头部信息 */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold mb-1">{detail.pipeline_name}</h3>
                <code className="text-xs text-gray-500">{detail.execution_id}</code>
              </div>
              {getStatusBadge(detail.status)}
            </div>

            <PipelineProgress
              current={detail.current_processor_index}
              total={detail.total_processors}
              status={detail.status}
            />
          </div>

          {/* 标签页 */}
          <Tabs
            items={tabItems}
            activeKey={activeTab}
            onChange={setActiveTab}
            className="mb-4"
          />

          {/* 标签内容 */}
          <div className="min-h-[300px]">
            {activeTab === 'basic' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-500 mb-1">流水线类型</label>
                    <p>{detail.pipeline_type}</p>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-500 mb-1">当前步骤</label>
                    <p>{detail.current_processor_index} / {detail.total_processors}</p>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-500 mb-1">创建时间</label>
                    <p>{detail.created_at ? new Date(detail.created_at).toLocaleString() : '-'}</p>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-500 mb-1">更新时间</label>
                    <p>{detail.updated_at ? new Date(detail.updated_at).toLocaleString() : '-'}</p>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-500 mb-1">完成时间</label>
                    <p>{detail.completed_at ? new Date(detail.completed_at).toLocaleString() : '-'}</p>
                  </div>
                  {detail.error_message && (
                    <div className="col-span-2">
                      <label className="block text-sm text-red-500 mb-1">错误信息</label>
                      <p className="text-red-600 bg-red-50 p-2 rounded">{detail.error_message}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'flow' && (
              <div>
                <PipelineFlowChart
                  processors={processors}
                  currentIndex={detail.current_processor_index}
                />
              </div>
            )}

            {activeTab === 'params' && (
              <div>
                <label className="block text-sm text-gray-500 mb-2">输入参数</label>
                <JsonViewer data={detail.input_params} />
              </div>
            )}

            {activeTab === 'context' && (
              <div>
                <label className="block text-sm text-gray-500 mb-2">上下文数据</label>
                <JsonViewer data={detail.context_data} />
              </div>
            )}

            {activeTab === 'result' && (
              <div>
                <label className="block text-sm text-gray-500 mb-2">执行结果</label>
                <JsonViewer data={detail.result} />
              </div>
            )}

            {activeTab === 'errors' && (
              <div>
                <label className="block text-sm text-gray-500 mb-2">错误列表</label>
                {detail.errors && detail.errors.length > 0 ? (
                  <div className="space-y-2">
                    {detail.errors.map((error, index) => (
                      <div key={index} className="bg-red-50 p-3 rounded text-red-700 text-sm">
                        <p className="font-medium">{error.message}</p>
                        {error.stack && (
                          <pre className="text-xs mt-1 overflow-x-auto">{error.stack}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">无错误信息</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
