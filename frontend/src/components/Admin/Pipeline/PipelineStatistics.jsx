import { Workflow, Play, CheckCircle, Clock } from 'lucide-react'

const StatCard = ({ title, value, icon, color, unit = '' }) => {
  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <p className="text-2xl font-semibold">
            {value}
            {unit && <span className="text-sm ml-1 text-gray-500">{unit}</span>}
          </p>
        </div>
        <div className={`p-3 rounded-full ${color} bg-opacity-10`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

export default function PipelineStatistics({ statistics }) {
  if (!statistics) return null

  const { total, running, success_rate, avg_duration } = statistics

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
      <StatCard
        title="总执行次数"
        value={total}
        icon={<Workflow className="w-5 h-5 text-blue-600" />}
        color="text-blue-600"
      />
      <StatCard
        title="运行中"
        value={running}
        icon={<Play className="w-5 h-5 text-yellow-600" />}
        color="text-yellow-600"
      />
      <StatCard
        title="成功率"
        value={success_rate}
        unit="%"
        icon={<CheckCircle className="w-5 h-5 text-green-600" />}
        color="text-green-600"
      />
      <StatCard
        title="平均执行时间"
        value={avg_duration}
        unit="s"
        icon={<Clock className="w-5 h-5 text-purple-600" />}
        color="text-purple-600"
      />
    </div>
  )
}
