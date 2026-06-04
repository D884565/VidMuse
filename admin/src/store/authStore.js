import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getToken, setToken, removeToken, getUserInfo, setUserInfo } from '@/utils/auth'
import { login as loginApi, logout as logoutApi, getProfile } from '@/services/auth'

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: getToken(),
      userInfo: getUserInfo(),
      isLoggedIn: !!getToken(),

      login: async (credentials) => {
        try {
          const { token, user } = await loginApi(credentials)
          setToken(token)
          setUserInfo(user)
          set({ token, userInfo: user, isLoggedIn: true })
          return { success: true }
        } catch (error) {
          return {
            success: false,
            message: error.response?.data?.message || '登录失败'
          }
        }
      },

      logout: async () => {
        try {
          await logoutApi()
        } catch (error) {
          console.error('登出接口调用失败', error)
        } finally {
          removeToken()
          set({ token: null, userInfo: null, isLoggedIn: false })
        }
      },

      fetchProfile: async () => {
        try {
          const user = await getProfile()
          setUserInfo(user)
          set({ userInfo: user })
          return user
        } catch (error) {
          console.error('获取用户信息失败', error)
          return null
        }
      }
    }),
    {
      name: 'auth-storage',
    }
  )
)

export default useAuthStore
