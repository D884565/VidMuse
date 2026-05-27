import { create } from 'zustand'

export const useAppStore = create((set) => ({
  activeView: 'chat',
  sidebarCollapsed: false,
  activeProjectId: 'p-001',
  isLoggedIn: !!localStorage.getItem('token'),
  parameters: {
    aspectRatio: '16:9',
    duration: 10,
    quality: 'cinematic',
  },
  setActiveView: (activeView) => set({ activeView }),
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveProjectId: (activeProjectId) => set({ activeProjectId }),
  login: (token) => {
    localStorage.setItem('token', token)
    set({ isLoggedIn: true })
  },
  setIsLoggedIn: (isLoggedIn) => set({ isLoggedIn }),
  logout: () => {
    localStorage.removeItem('token')
    set({ isLoggedIn: false })
  },
  updateParameters: (patch) =>
    set((state) => ({ parameters: { ...state.parameters, ...patch } })),
}))
