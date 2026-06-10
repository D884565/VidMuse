import { CheckCircle, AlertCircle, Clock, PlayCircle } from 'lucide-react'

const ProcessorNode = ({ name, status, index, isLast }) => {
  const getIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      case 'running':
        return <PlayCircle className="w-5 h-5 text-blue-500 animate-pulse" />
      default:
        return <Clock className="w-5 h-5 text-gray-400" />
    }
  }

  const getLineColor = () => {
    if (status === 'completed') return 'bg-green-500'
    if (status === 'failed') return 'bg-red-500'
    return 'bg-gray-200'
  }

  return (
    <div className="flex items-center">
      <div className="flex flex-col items-center">
        <div className="rounded-full bg-white p-1 border border-gray-200">
          {getIcon()}
        </div>
        <div className="text-xs mt-1 text-center max-w-[100px] break-words">
          {name}
        </div>
      </div>
      {!isLast && (
        <div className={`w-12 h-0.5 mx-2 ${getLineColor()}`} />
      )}
    </div>
  )
}

export default function PipelineFlowChart({ processors = [], currentIndex = 0 }) {
  if (!processors.length) return null

  // 确定每个处理器的状态
  const getProcessorStatus = (index) => {
    if (index < currentIndex) return 'completed'
    if (index === currentIndex) return 'running'
    return 'pending'
  }

  return (
    <div className="flex items-center justify-center p-4 bg-gray-50 rounded-lg overflow-x-auto">
      <div className="flex items-center min-w-max">
        {processors.map((processor, index) => (
          <ProcessorNode
            key={index}
            name={processor.name || `处理器 ${index + 1}`}
            status={getProcessorStatus(index)}
            index={index}
            isLast={index === processors.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
