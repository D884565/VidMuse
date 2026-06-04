import { Navigate } from 'react-router-dom'
import { useAppStore } from '../store/appStore'

export default function AuthGuard({ children, requiredRole }) {
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)
  const user = useAppStore((state) => state.user)
  const authLoading = useAppStore((state) => state.authLoading)

  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--bg-main)] text-sm text-[var(--text-muted)]">
        正在验证权限...
      </div>
    )
  }

  // 未登录跳转到首页
  if (!isLoggedIn) {
    return <Navigate to="/" replace />
  }

  // 校验角色权限
  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to="/403" replace />
  }

  return children
}
