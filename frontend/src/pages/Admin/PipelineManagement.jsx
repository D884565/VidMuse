import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Wifi, WifiOff } from 'lucide-react'
import PageContainer from '@/components/Admin/Layout/PageContainer'
import Button from '@/components/Button/Button'
import PipelineFilter from '@/components/Admin/Pipeline/PipelineFilter'
import PipelineStatistics from '@/components/Admin/Pipeline/PipelineStatistics'
import PipelineList from '@/components/Admin/Pipeline/PipelineList'
import PipelineDetailModal from '@/components/Admin/Pipeline/PipelineDetailModal'
import { usePipelinePush } from '@/hooks/usePipelinePush'
import {
  getPipelineList,
  getPipelineStatistics,
  retryPipeline,
  cancelPipeline
} from '@/services/admin'

export default function PipelineManagement() {
  const [filters, setFilters] = useState({
    page: 1,
    page_size: 10,
    status: '',
    pipeline_type: '',
    keyword: '',
    start_time: null,
    end_time: null
  })
  const [listData, setListData] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [statistics, setStatistics] = useState(null)
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedExecution, setSelectedExecution] = useState(null)

  // 处理推送更新
  const handlePushUpdate = useCallback((update) => {
    // 更新列表中的对应记录
    setListData(prev => {
      const index = prev.findIndex(item => item.execution_id === update.execution_id)
      if (index !== -1) {
        // 更新现有记录
        const newList = [...prev]
        newList[index] = { ...newList[index], ...update }
        return newList
      } else {
        // 新记录添加到顶部
        return [update, ...prev]
      }
    })

    // 重新加载统计数据
    loadStatistics()

    // 显示通知
    alert(`流水线 ${update.pipeline_name} 状态更新为: ${update.status}`)
  }, [])

  const { isConnected, error } = usePipelinePush({ onUpdate: handlePushUpdate })

  // 加载列表数据
  const loadList = useCallback(async () => {
    try {
      setLoading(true)
      const res = await getPipelineList(filters)
      setListData(res.list)
      setTotal(res.total)
    } catch (error) {
      alert('加载列表失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  // 加载统计数据
  const loadStatistics = useCallback(async () => {
    try {
      const res = await getPipelineStatistics()
      setStatistics(res)
    } catch (error) {
      console.error('加载统计数据失败:', error)
    }
  }, [])

  useEffect(() => {
    loadList()
    loadStatistics()
  }, [filters])

  // 处理筛选变化
  const handleFilterChange = (newFilters) => {
    setFilters({ ...newFilters, page: 1 })
  }

  // 处理重置筛选
  const handleReset = () => {
    setFilters({
      page: 1,
      page_size: 10,
      status: '',
      pipeline_type: '',
      keyword: '',
      start_time: null,
      end_time: null
    })
  }

  // 处理分页变化
  const handlePageChange = (page, pageSize) => {
    setFilters(prev => ({ ...prev, page, page_size: pageSize }))
  }

  // 处理刷新
  const handleRefresh = () => {
    loadList()
    loadStatistics()
    alert('已刷新')
  }

  // 处理查看详情
  const handleViewDetail = (record) => {
    setSelectedExecution(record)
    setDetailVisible(true)
  }

  // 处理重试
  const handleRetry = async (record) => {
    if (window.confirm(`确定要重试流水线 "${record.pipeline_name}" 吗？`)) {
      try {
        await retryPipeline(record.execution_id)
        alert('已提交重试')
        loadList()
      } catch (error) {
        alert('重试失败: ' + error.message)
      }
    }
  }

  // 处理取消
  const handleCancel = async (record) => {
    if (window.confirm(`确定要取消流水线 "${record.pipeline_name}" 吗？`)) {
      try {
        await cancelPipeline(record.execution_id)
        alert('已取消')
        loadList()
      } catch (error) {
        alert('取消失败: ' + error.message)
      }
    }
  }

  return (
    <PageContainer
      title="流水线管理"
      extra={
        <div className="flex items-center gap-2">
          {/* 连接状态指示 */}
          <div className="flex items-center gap-1 text-sm">
            {isConnected ? (
              <>
                <Wifi className="w-4 h-4 text-green-500" />
                <span className="text-green-600">已连接</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-red-500" />
                <span className="text-red-600">未连接</span>
              </>
            )}
          </div>

          <Button
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={handleRefresh}
            loading={loading}
          >
            刷新
          </Button>
        </div>
      }
    >
      {/* 统计卡片 */}
      <PipelineStatistics statistics={statistics} />

      {/* 筛选栏 */}
      <PipelineFilter
        filters={filters}
        onFilterChange={handleFilterChange}
        onReset={handleReset}
      />

      {/* 列表 */}
      <PipelineList
        data={listData}
        loading={loading}
        pagination={{
          page: filters.page,
          page_size: filters.page_size,
          total
        }}
        onPageChange={handlePageChange}
        onViewDetail={handleViewDetail}
        onRetry={handleRetry}
        onCancel={handleCancel}
      />

      {/* 详情模态框 */}
      <PipelineDetailModal
        visible={detailVisible}
        executionId={selectedExecution?.execution_id}
        onClose={() => setDetailVisible(false)}
      />
    </PageContainer>
  )
}
