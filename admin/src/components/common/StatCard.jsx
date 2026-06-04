import { TrendingUp, TrendingDown } from 'lucide-react'

function StatCard({ title, value, trend, trendValue, icon, color = 'primary' }) {
  const colorClasses = {
    primary: 'bg-primary/10 text-primary',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-warning',
    danger: 'bg-danger/10 text-danger',
  }

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-300 mb-1">{title}</p>
          <h3 className="text-2xl font-bold text-gray-500">{value}</h3>
          {trend && (
            <div className="flex items-center mt-2">
              {trend === 'up' ? (
                <TrendingUp size={14} className="text-success mr-1" />
              ) : (
                <TrendingDown size={14} className="text-danger mr-1" />
              )}
              <span
                className={`text-xs font-medium ${
                  trend === 'up' ? 'text-success' : 'text-danger'
                }`}
              >
                {trendValue}
              </span>
              <span className="text-xs text-gray-300 ml-1">较昨日</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

export default StatCard
