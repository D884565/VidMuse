/** 管理后台页面容器 — 统一的标题栏 + 操作按钮 + 内容区域布局 */
export default function PageContainer({ title, children, actions }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">{title}</h1>
        {actions && <div>{actions}</div>}
      </div>
      {children}
    </div>
  )
}
