export default function PageContainer({ title, children, actions }) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">{title}</h1>
        {actions && <div>{actions}</div>}
      </div>
      {children}
    </div>
  )
}
