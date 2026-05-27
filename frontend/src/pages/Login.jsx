import { useState } from 'react'
import { useAppStore } from '../store/appStore.js'
import { login, register } from '../services/auth.js'

export default function Login() {
  const [activeTab, setActiveTab] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const loginAction = useAppStore((state) => state.login)

  // 切换标签时清空表单和错误信息
  const switchTab = (tab) => {
    setActiveTab(tab)
    setError('')
    setUsername('')
    setPassword('')
    setConfirmPassword('')
  }

  // 处理登录
  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password.trim()) {
      setError('请填写用户名和密码')
      return
    }

    setLoading(true)
    try {
      const data = await login(username, password)
      loginAction(data.access_token)
    } catch (err) {
      setError(err.message || '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  // 处理注册
  const handleRegister = async (e) => {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password.trim()) {
      setError('请填写用户名和密码')
      return
    }

    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }

    setLoading(true)
    try {
      const data = await register(username, password)
      // 注册成功后自动登录
      loginAction(data.access_token)
    } catch (err) {
      setError(err.message || '注册失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-main)] flex items-center justify-center">
      <div className="w-full max-w-md px-6">
        {/* 标题 */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">VidMuse</h1>
          <p className="text-gray-400">AI 视频创作平台</p>
        </div>

        {/* 登录/注册卡片 */}
        <div className="bg-[var(--bg-secondary)] rounded-xl p-8 shadow-lg">
          {/* 标签切换 */}
          <div className="flex mb-6 border-b border-gray-700">
            <button
              className={`flex-1 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'login'
                  ? 'text-[#7C3AED] border-b-2 border-[#7C3AED]'
                  : 'text-gray-400 hover:text-white'
              }`}
              onClick={() => switchTab('login')}
            >
              登录
            </button>
            <button
              className={`flex-1 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'register'
                  ? 'text-[#7C3AED] border-b-2 border-[#7C3AED]'
                  : 'text-gray-400 hover:text-white'
              }`}
              onClick={() => switchTab('register')}
            >
              注册
            </button>
          </div>

          {/* 错误信息 */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* 登录表单 */}
          {activeTab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  placeholder="请输入用户名"
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  密码
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  placeholder="请输入密码"
                  autoComplete="current-password"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              >
                {loading ? '登录中...' : '登录'}
              </button>
            </form>
          )}

          {/* 注册表单 */}
          {activeTab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  placeholder="请输入用户名"
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  密码
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  placeholder="请输入密码"
                  autoComplete="new-password"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  确认密码
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  placeholder="请再次输入密码"
                  autoComplete="new-password"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              >
                {loading ? '注册中...' : '注册'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
