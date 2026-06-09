import { create } from 'zustand'

export const useAppStore = create((set, get) => ({
  activeView: 'chat',
  sidebarCollapsed: false,
  activeProjectId: null,
  draftConversationTitle: '',
  draftConversationMessages: [],
  projectListVersion: 0,
  conversationVersion: 0,
  creationMode: 'independent',
  isLoggedIn: !!localStorage.getItem('token'),
  authLoading: false,
  // 用户信息（会话内有效，可通过 /users/me 刷新）
  user: null,
  // refresh_token 存 localStorage 实现跨会话持久化
  parameters: {
    style: 'product',
    voice_type: 'zh_female_cancan_mars_bigtts',
    target_duration: 15,
    rag_weight: 0.3,
  },
  setActiveView: (activeView) => set({ activeView }),
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveProjectId: (activeProjectId) => set({ activeProjectId }),
  setDraftConversationTitle: (draftConversationTitle) => set({ draftConversationTitle }),
  setDraftConversationMessages: (draftConversationMessages) =>
    set((state) => ({
      draftConversationMessages:
        typeof draftConversationMessages === 'function'
          ? draftConversationMessages(state.draftConversationMessages)
          : draftConversationMessages,
    })),
  clearDraftConversation: () => set({ draftConversationTitle: '', draftConversationMessages: [] }),
  bumpProjectListVersion: () => set((state) => ({ projectListVersion: state.projectListVersion + 1 })),
  bumpConversationVersion: () => set((state) => ({ conversationVersion: state.conversationVersion + 1 })),
  setCreationMode: (creationMode) => set({ creationMode }),
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

    // 确保用户信息中的role是数字类型
    const normalizedUserInfo = userInfo ? {
      ...userInfo,
      role: Number(userInfo.role)
    } : null

    set({ isLoggedIn: true, user: normalizedUserInfo, authLoading: false })
    console.log('[Store] 用户登录成功，用户信息:', normalizedUserInfo)
  },
  setIsLoggedIn: (isLoggedIn) => set({ isLoggedIn }),
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    set({
      isLoggedIn: false,
      user: null,
      authLoading: false,
      draftConversationTitle: '',
      draftConversationMessages: [],
      activeProjectId: null,
    })
  },
  updateParameters: (patch) =>
    set((state) => ({ parameters: { ...state.parameters, ...patch } })),

  // 管理员权限判断
  isAdmin: () => {
    const user = get().user
    return user?.role === 0
  },

  // 管理员相关状态
  userList: [],
  setUserList: (users) => set({ userList: users }),
}))
