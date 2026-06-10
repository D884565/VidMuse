export default function PipelineProgress({ current, total, status, size = 'default' }) {
  const progress = total > 0 ? Math.min(Math.round((current / total) * 100), 100) : 0

  // 根据状态确定进度条颜色
  const getProgressColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'cancelled':
        return 'bg-yellow-500'
      case 'running':
        return 'bg-blue-500 animate-pulse'
      default:
        return 'bg-gray-300'
    }
  }

  const heightClass = size === 'small' ? 'h-1.5' : 'h-2'

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500">
          {current > 0 ? `步骤 ${current}/${total}` : ''}
        </span>
        <span className="text-xs font-medium">{progress}%</span>
      </div>
      <div className={`w-full bg-gray-200 rounded-full ${heightClass}`}>
        <div
          className={`${getProgressColor()} ${heightClass} rounded-full transition-all duration-500`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
