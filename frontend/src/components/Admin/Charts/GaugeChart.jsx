import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

export default function GaugeChart({ value, title, max = 100, color = '#3b82f6' }) {
  const data = [
    { name: 'value', value: value },
    { name: 'empty', value: max - value },
  ]

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
      <div className="relative h-48 flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              startAngle={180}
              endAngle={0}
              innerRadius="70%"
              outerRadius="90%"
              dataKey="value"
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill="#e5e7eb" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-gray-800">{value}%</span>
          <span className="text-sm text-gray-500">使用率</span>
        </div>
      </div>
    </div>
  )
}
