import { ArrowUp, ArrowDown } from 'lucide-react'

/**
 * 统计卡片组件
 * @param {string} title 卡片标题
 * @param {number|string} value 统计值
 * @param {string} [unit] 单位
 * @param {number} [trend] 趋势值，正数上升，负数下降
 * @param {string} [trendText] 趋势说明
 * @param {React.ReactNode} [icon] 图标
 * @param {string} [className] 自定义类名
 */
export default function StatCard({ title, value, unit, trend, trendText, icon, className = '' }) {
  const isPositive = trend > 0
  const isNegative = trend < 0

  return (
    <div className={`bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] p-5 ${className}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-[var(--text-muted)] mb-1">{title}</p>
          <div className="flex items-baseline gap-1">
            <h3 className="text-2xl font-semibold">{value}</h3>
            {unit && <span className="text-sm text-[var(--text-muted)]">{unit}</span>}
          </div>
          {trend !== undefined && (
            <div className={`flex items-center gap-1 text-xs mt-2 ${
              isPositive ? 'text-green-500' : isNegative ? 'text-red-500' : 'text-[var(--text-muted)]'
            }`}>
              {isPositive && <ArrowUp size={12} />}
              {isNegative && <ArrowDown size={12} />}
              <span>{Math.abs(trend)}%</span>
              {trendText && <span className="text-[var(--text-muted)] ml-1">{trendText}</span>}
            </div>
          )}
        </div>
        {icon && (
          <div className="p-3 bg-[var(--brand-soft)] rounded-lg text-white">
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
