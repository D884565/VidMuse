function PageContainer({ title, children, className = '', extra = null }) {
  return (
    <div className={`p-6 ${className}`}>
      {/* 页面头部 */}
      {(title || extra) && (
        <div className="flex justify-between items-center mb-6">
          {title && <h1 className="text-2xl font-bold text-gray-500">{title}</h1>}
          {extra && <div>{extra}</div>}
        </div>
      )}

      {/* 页面内容 */}
      {children}
    </div>
  )
}

export default PageContainer
