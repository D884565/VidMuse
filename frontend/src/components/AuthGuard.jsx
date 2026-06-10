import { useEffect, useCallback } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAppStore } from '../store/appStore'
import { getUserInfo } from '../services/user.js'

// 角色映射：角色名称到数字值
const ROLE_MAP = {
  admin: 0,
  user: 1,
  vip: 2
}

export default function AuthGuard({ children, requiredRole }) {
  const location = useLocation()
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)
  const user = useAppStore((state) => state.user)
  const authLoading = useAppStore((state) => state.authLoading)
  const setUser = useAppStore((state) => state.setUser)
  const setAuthLoading = useAppStore((state) => state.setAuthLoading)
  const logout = useAppStore((state) => state.logout)

  // 安全的用户信息加载函数
  const loadUserInfo = useCallback(async () => {
    if (!isLoggedIn || user) return

    try {
      setAuthLoading(true)
      console.log('[AuthGuard] 开始加载用户信息...')
      const data = await getUserInfo()
      console.log('[AuthGuard] 用户信息加载成功:', data)

      // 确保role是数字类型
      const userData = {
        id: data.id,
        username: data.username,
        role: Number(data.role)
      }

      setUser(userData)
      console.log('[AuthGuard] 用户信息已保存到store:', userData)
    } catch (error) {
      console.error('[AuthGuard] 用户信息加载失败:', error)
      // token 已失效，清除登录状态
      logout()
    } finally {
      setAuthLoading(false)
      console.log('[AuthGuard] 加载流程结束, authLoading:', false)
    }
  }, [isLoggedIn, user, setUser, setAuthLoading, logout])

  // 页面刷新后恢复用户信息
  useEffect(() => {
    loadUserInfo()
  }, [loadUserInfo])

  // 调试日志
  useEffect(() => {
    console.log('[AuthGuard] 状态更新:', {
      path: location.pathname,
      isLoggedIn,
      hasUser: !!user,
      userRole: user?.role,
      authLoading,
      requiredRole
    })
  }, [location.pathname, isLoggedIn, user, authLoading, requiredRole])

  // 加载中显示加载页（根据路由适配主题）
  if (authLoading) {
    const isAdminRoute = location.pathname.startsWith('/admin')
    return (
      <div className={`grid min-h-screen place-items-center text-sm ${
        isAdminRoute ? 'bg-white text-gray-600' : 'bg-[var(--bg-main)] text-gray-400'
      }`}>
        <div className="text-center">
          <div className="mb-2">正在验证权限...</div>
          <div className="text-xs opacity-75">路径: {location.pathname}</div>
        </div>
      </div>
    )
  }

  // 未登录跳转到首页
  if (!isLoggedIn) {
    console.log('[AuthGuard] 未登录，跳转到首页')
    return <Navigate to="/" replace />
  }

  // 如果需要角色校验但用户信息还没加载完成，继续加载
  if (requiredRole && !user) {
    console.log('[AuthGuard] 需要角色校验但用户信息未加载，重新触发加载')
    loadUserInfo()
    const isAdminRoute = location.pathname.startsWith('/admin')
    return (
      <div className={`grid min-h-screen place-items-center text-sm ${
        isAdminRoute ? 'bg-white text-gray-600' : 'bg-[var(--bg-main)] text-gray-400'
      }`}>
        <div className="text-center">
          <div className="mb-2">正在加载用户信息...</div>
          <div className="text-xs opacity-75">请稍候</div>
        </div>
      </div>
    )
  }

  // 校验角色权限
  if (requiredRole) {
    const requiredRoleValue = typeof requiredRole === 'number' ? requiredRole : ROLE_MAP[requiredRole]
    const userRole = Number(user?.role)

    console.log('[AuthGuard] 角色校验:', {
      requiredRole,
      requiredRoleValue,
      userRole,
      match: userRole === requiredRoleValue
    })

    if (requiredRoleValue === undefined || userRole !== requiredRoleValue) {
      console.warn('[AuthGuard] 权限校验不通过，跳转到403')
      return <Navigate to="/403" replace />
    }

    console.log('[AuthGuard] 权限校验通过，允许访问')
  }

  return children
}
