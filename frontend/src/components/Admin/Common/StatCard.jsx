import { ArrowUp, ArrowDown } from 'lucide-react'

export default function StatCard({ title, value, trend, trendValue, icon: Icon, color = 'blue' }) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <h3 className="text-2xl font-bold text-gray-800">{value}</h3>
          {trend && (
            <div className="flex items-center mt-2 text-sm">
              {trend === 'up' ? (
                <ArrowUp size={16} className="text-green-500 mr-1" />
              ) : (
                <ArrowDown size={16} className="text-red-500 mr-1" />
              )}
              <span className={trend === 'up' ? 'text-green-500' : 'text-red-500'}>
                {trendValue}%
              </span>
              <span className="text-gray-500 ml-1">较上月</span>
            </div>
          )}
        </div>
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${colorClasses[color]}`}>
          <Icon size={24} />
        </div>
      </div>
    </div>
  )
}
