import { useState, useEffect } from 'react'
import { User, Lock, LogOut, Loader2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore.js'
import { getUserInfo, updateUserInfo, changePassword } from '../../services/user.js'
import { logoutApi } from '../../services/user.js'

export default function UserProfile() {
  const user = useAppStore((state) => state.user)
  const setUser = useAppStore((state) => state.setUser)
  const storeLogout = useAppStore((state) => state.logout)

  const [userInfo, setUserInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [username, setUsername] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // 密码修改
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  useEffect(() => {
    getUserInfo()
      .then((data) => {
        setUserInfo(data)
        setUsername(data.username)
        setUser(data)
      })
      .catch((err) => console.warn('获取用户信息失败:', err.message))
      .finally(() => setLoading(false))
  }, [setUser])

  const handleSaveUsername = async () => {
    if (!username.trim() || username.trim().length < 2) {
      setError('用户名至少 2 个字符')
      return
    }
    setSaving(true)
    setError('')
    try {
      await updateUserInfo({ username: username.trim() })
      setUserInfo((prev) => ({ ...prev, username: username.trim() }))
      setUser({ ...userInfo, username: username.trim() })
      setEditing(false)
      setSuccess('用户名已更新')
      setTimeout(() => setSuccess(''), 2000)
    } catch (err) {
      setError(err.message || '更新失败')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    setError('')
    if (!oldPassword || !newPassword) {
      setError('请填写旧密码和新密码')
      return
    }
    if (newPassword.length < 8 || newPassword.length > 32) {
      setError('新密码长度为 8-32 个字符')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    setSaving(true)
    try {
      await changePassword(oldPassword, newPassword)
      setSuccess('密码修改成功')
      setShowPasswordForm(false)
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => setSuccess(''), 2000)
    } catch (err) {
      setError(err.message || '密码修改失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch (err) {
      // 忽略退出接口错误，本地仍清除状态
    }
    storeLogout()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="animate-spin text-[#7C3AED]" size={24} />
      </div>
    )
  }

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6">
        <h1 className="m-0 text-lg font-semibold">个人信息</h1>
        <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">管理你的账户信息</p>
      </header>

      {/* 成功/错误提示 */}
      {success && (
        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
          {success}
        </div>
      )}
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* 用户信息卡片 */}
      <div className="max-w-lg rounded-xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-6 mb-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-[rgba(124,58,237,0.24)] text-xl font-semibold">
            {userInfo?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <p className="text-base font-medium">{userInfo?.username}</p>
            <p className="text-xs text-[var(--text-muted)]">{userInfo?.role_name || '用户'}</p>
            {userInfo?.created_at && (
              <p className="text-xs text-[var(--text-muted)]">
                注册于 {new Date(userInfo.created_at).toLocaleDateString('zh-CN')}
              </p>
            )}
          </div>
        </div>

        {/* 用户名编辑 */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-1.5">用户名</label>
          {editing ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="flex-1 px-3 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED]"
                minLength={2}
                maxLength={50}
              />
              <button
                onClick={handleSaveUsername}
                disabled={saving}
                className="px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 text-white rounded-lg text-sm"
              >
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                onClick={() => { setEditing(false); setUsername(userInfo?.username || ''); setError('') }}
                className="px-4 py-2 border border-gray-700 text-gray-300 hover:bg-gray-700/50 rounded-lg text-sm"
              >
                取消
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm">{userInfo?.username}</span>
              <button
                onClick={() => setEditing(true)}
                className="text-xs text-[#a78bfa] hover:text-white"
              >
                编辑
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="max-w-lg space-y-3">
        <button
          onClick={() => { setShowPasswordForm(!showPasswordForm); setError('') }}
          className="flex w-full items-center gap-3 rounded-lg border border-[var(--border-soft)] px-4 py-3 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white transition-colors"
        >
          <Lock size={18} />
          修改密码
        </button>

        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg border border-red-500/30 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut size={18} />
          退出登录
        </button>
      </div>

      {/* 密码修改表单 */}
      {showPasswordForm && (
        <div className="max-w-lg mt-4 rounded-xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-6">
          <h3 className="text-sm font-medium mb-4">修改密码</h3>
          <div className="space-y-3">
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED]"
              placeholder="当前密码"
              autoComplete="current-password"
            />
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED]"
              placeholder="新密码（8-32字符）"
              autoComplete="new-password"
            />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED]"
              placeholder="确认新密码"
              autoComplete="new-password"
            />
            <div className="flex gap-2 pt-1">
              <button
                onClick={handleChangePassword}
                disabled={saving}
                className="px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 text-white rounded-lg text-sm"
              >
                {saving ? '修改中...' : '确认修改'}
              </button>
              <button
                onClick={() => { setShowPasswordForm(false); setOldPassword(''); setNewPassword(''); setConfirmPassword(''); setError('') }}
                className="px-4 py-2 border border-gray-700 text-gray-300 hover:bg-gray-700/50 rounded-lg text-sm"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
