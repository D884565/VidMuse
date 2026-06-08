import { Eye, RefreshCw, XCircle } from 'lucide-react'
import Table from '@/components/Admin/Common/Table'
import Button from '@/components/Button/Button'
import Badge from '@/components/Badge/Badge'
import PipelineProgress from './PipelineProgress'

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

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
  return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
}

export default function PipelineList({
  data,
  loading,
  pagination,
  onPageChange,
  onViewDetail,
  onRetry,
  onCancel
}) {
  const columns = [
    {
      key: 'execution_id',
      title: '执行ID',
      width: 180,
      render: (id) => <code className="text-xs text-gray-600">{id}</code>
    },
    {
      key: 'pipeline_name',
      title: '流水线名称',
      width: 200,
      render: (name) => <span className="font-medium">{name}</span>
    },
    {
      key: 'pipeline_type',
      title: '类型',
      width: 120,
      render: (type) => {
        const typeMap = {
          video: '视频处理',
          product: '商品处理',
          video_overall: '视频综合'
        }
        return <span>{typeMap[type] || type}</span>
      }
    },
    {
      key: 'status',
      title: '状态',
      width: 100,
      render: (status) => getStatusBadge(status)
    },
    {
      key: 'progress',
      title: '进度',
      width: 200,
      render: (_, row) => (
        <PipelineProgress
          current={row.current_processor_index}
          total={row.total_processors}
          status={row.status}
          size="small"
        />
      )
    },
    {
      key: 'duration',
      title: '耗时',
      width: 100,
      render: (_, row) => {
        if (!row.created_at) return '-'
        const startTime = new Date(row.created_at)
        const endTime = row.completed_at ? new Date(row.completed_at) : new Date()
        const duration = (endTime - startTime) / 1000
        return formatDuration(duration)
      }
    },
    {
      key: 'created_at',
      title: '创建时间',
      width: 180,
      render: (time) => time ? new Date(time).toLocaleString() : '-'
    },
    {
      key: 'actions',
      title: '操作',
      width: 150,
      fixed: 'right',
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <Button
            type="text"
            size="small"
            icon={<Eye className="w-4 h-4" />}
            onClick={() => onViewDetail(row)}
            title="查看详情"
          />
          {row.status === 'failed' && (
            <Button
              type="text"
              size="small"
              icon={<RefreshCw className="w-4 h-4 text-green-600" />}
              onClick={() => onRetry(row)}
              title="重试"
            />
          )}
          {['pending', 'running'].includes(row.status) && (
            <Button
              type="text"
              size="small"
              icon={<XCircle className="w-4 h-4 text-red-600" />}
              onClick={() => onCancel(row)}
              title="取消"
            />
          )}
        </div>
      )
    }
  ]

  return (
    <div className="bg-white rounded-lg shadow-sm">
      <Table
        columns={columns}
        dataSource={data}
        loading={loading}
        rowKey="execution_id"
        pagination={{
          current: pagination.page,
          pageSize: pagination.page_size,
          total: pagination.total,
          onChange: onPageChange
        }}
      />
    </div>
  )
}