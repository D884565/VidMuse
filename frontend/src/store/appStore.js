import { create } from 'zustand'

export const useAppStore = create((set, get) => ({
  activeView: 'chat',
  sidebarCollapsed: false,
  activeProjectId: null,
  projectListVersion: 0,
  isLoggedIn: !!localStorage.getItem('token'),
  authLoading: !!localStorage.getItem('token'),
  // 用户信息（会话内有效，可通过 /users/me 刷新）
  user: null,
  // 新增：判断当前用户是否为管理员
  isAdmin: () => get().user?.role === 'admin',
  // refresh_token 存 localStorage 实现跨会话持久化
  parameters: {
    style: 'cinematic',
    target_duration: 15,
    rag_weight: 0.3,
  },
  setActiveView: (activeView) => set({ activeView }),
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveProjectId: (activeProjectId) => set({ activeProjectId }),
  bumpProjectListVersion: () => set((state) => ({ projectListVersion: state.projectListVersion + 1 })),
  setUser: (user) => set({ user }),
  setAuthLoading: (authLoading) => set({ authLoading }),
  setRefreshToken: (refreshToken) => {
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken)
    } else {
      localStorage.removeItem('refresh_token')
    }
  },
  login: (token, refreshToken, userInfo) => {
    localStorage.setItem('token', token)
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken)
    set({ isLoggedIn: true, user: userInfo || null, authLoading: false })
  },
  setIsLoggedIn: (isLoggedIn) => set({ isLoggedIn }),
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    set({ isLoggedIn: false, user: null, authLoading: false })
  },
  updateParameters: (patch) =>
    set((state) => ({ parameters: { ...state.parameters, ...patch } })),
}))
