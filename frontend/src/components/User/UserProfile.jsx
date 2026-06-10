import { useEffect, useState } from 'react'
import { Loader2, Lock, LogOut, Save } from 'lucide-react'
import { useAppStore } from '../../store/appStore.js'
import { changePassword, getUserInfo, logoutApi, updateUserInfo } from '../../services/user.js'

/** 个人资料页面 — 查看/编辑用户信息、修改密码、退出登录 */
export default function UserProfile() {
  const setUser = useAppStore((state) => state.setUser)
  const storeLogout = useAppStore((state) => state.logout)

  const [userInfo, setUserInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [username, setUsername] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  useEffect(() => {
    getUserInfo()
      .then((data) => {
        setUserInfo(data)
        setUsername(data.username || '')
        setUser(data)
      })
      .catch((err) => {
        setError(err.message || '获取用户信息失败')
      })
      .finally(() => setLoading(false))
  }, [setUser])

  const resetMessageLater = (setter) => {
    window.setTimeout(() => setter(''), 2200)
  }

  const handleSaveUsername = async () => {
    if (!username.trim() || username.trim().length < 2) {
      setError('用户名至少需要 2 个字符')
      return
    }

    setSaving(true)
    setError('')

    try {
      await updateUserInfo({ username: username.trim() })
      const nextUser = { ...userInfo, username: username.trim() }
      setUserInfo(nextUser)
      setUser(nextUser)
      setEditing(false)
      setSuccess('个人信息已更新')
      resetMessageLater(setSuccess)
    } catch (err) {
      setError(err.message || '更新个人信息失败')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    setError('')

    if (!oldPassword || !newPassword) {
      setError('请填写当前密码和新密码')
      return
    }
    if (newPassword.length < 8 || newPassword.length > 32) {
      setError('新密码长度需为 8 到 32 个字符')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致')
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
      resetMessageLater(setSuccess)
    } catch (err) {
      setError(err.message || '密码修改失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch {
      // Ignore logout API errors and still clear the local session.
    }
    storeLogout()
  }

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--bg-main)]">
        <Loader2 className="animate-spin text-[#7C3AED]" size={28} />
      </div>
    )
  }

  const createdAtLabel = userInfo?.created_at
    ? new Date(userInfo.created_at).toLocaleDateString('zh-CN')
    : '暂无记录'

  return (
    <section className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(124,58,237,0.16),transparent_35%),var(--bg-main)] px-6 py-8 md:px-10">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8">
          <p className="m-0 text-xs uppercase tracking-[0.3em] text-[rgba(167,139,250,0.9)]">
            Account
          </p>
          <h1 className="m-0 mt-3 text-3xl font-semibold text-white">个人信息</h1>
          <p className="m-0 mt-2 text-sm text-[var(--text-muted)]">
            在这里修改你的账户资料和登录密码。
          </p>
        </header>

        {(success || error) && (
          <div
            className={`mb-6 rounded-2xl border px-4 py-3 text-sm ${
              success
                ? 'border-green-500/30 bg-green-500/10 text-green-300'
                : 'border-red-500/30 bg-red-500/10 text-red-300'
            }`}
          >
            {success || error}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[28px] border border-[var(--border-soft)] bg-[rgba(18,18,26,0.84)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.22)]">
            <div className="flex items-center gap-4">
              <div className="grid h-20 w-20 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] text-2xl font-semibold text-white shadow-[0_10px_30px_rgba(124,58,237,0.28)]">
                {userInfo?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="min-w-0">
                <p className="m-0 truncate text-xl font-medium text-white">{userInfo?.username || '未登录'}</p>
                <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
                  {userInfo?.role_name || '用户'}
                </p>
                <p className="m-0 mt-2 text-xs text-[var(--text-muted)]">
                  注册时间：{createdAtLabel}
                </p>
              </div>
            </div>

            <div className="mt-8 rounded-2xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.02)] p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="m-0 text-sm font-medium text-white">用户名</p>
                  <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
                    用于展示在侧栏头像区域。
                  </p>
                </div>
                {!editing && (
                  <button
                    className="rounded-full border border-[var(--border-soft)] px-3 py-1.5 text-xs text-[rgba(167,139,250,0.95)] transition hover:bg-[var(--brand-soft)] hover:text-white"
                    type="button"
                    onClick={() => {
                      setEditing(true)
                      setError('')
                    }}
                  >
                    编辑
                  </button>
                )}
              </div>

              {editing ? (
                <div className="mt-4 flex flex-col gap-3 md:flex-row">
                  <input
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    minLength={2}
                    maxLength={50}
                    className="h-11 flex-1 rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-4 text-sm text-white outline-none transition focus:border-[#7C3AED]"
                    placeholder="请输入用户名"
                  />
                  <div className="flex gap-2">
                    <button
                      className="inline-flex h-11 items-center gap-2 rounded-xl bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 text-sm font-medium text-white disabled:opacity-60"
                      type="button"
                      disabled={saving}
                      onClick={handleSaveUsername}
                    >
                      <Save size={16} />
                      {saving ? '保存中...' : '保存'}
                    </button>
                    <button
                      className="h-11 rounded-xl border border-[var(--border-soft)] px-4 text-sm text-[var(--text-muted)] transition hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                      type="button"
                      onClick={() => {
                        setEditing(false)
                        setUsername(userInfo?.username || '')
                        setError('')
                      }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <p className="m-0 mt-4 text-sm text-white">{userInfo?.username || '未设置'}</p>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[28px] border border-[var(--border-soft)] bg-[rgba(18,18,26,0.84)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[rgba(124,58,237,0.16)] text-[rgba(196,181,253,0.95)]">
                  <Lock size={18} />
                </div>
                <div>
                  <p className="m-0 text-sm font-medium text-white">密码与安全</p>
                  <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
                    需要时可以修改你的登录密码。
                  </p>
                </div>
              </div>

              <button
                className="mt-5 flex w-full items-center justify-center rounded-xl border border-[var(--border-soft)] px-4 py-3 text-sm text-[var(--text-muted)] transition hover:bg-[var(--brand-soft)] hover:text-white"
                type="button"
                onClick={() => {
                  setShowPasswordForm((open) => !open)
                  setError('')
                }}
              >
                {showPasswordForm ? '收起密码表单' : '修改密码'}
              </button>

              {showPasswordForm && (
                <div className="mt-5 space-y-3">
                  <input
                    type="password"
                    value={oldPassword}
                    onChange={(event) => setOldPassword(event.target.value)}
                    className="h-11 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-4 text-sm text-white outline-none transition focus:border-[#7C3AED]"
                    placeholder="当前密码"
                    autoComplete="current-password"
                  />
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    className="h-11 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-4 text-sm text-white outline-none transition focus:border-[#7C3AED]"
                    placeholder="新密码（8-32 个字符）"
                    autoComplete="new-password"
                  />
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="h-11 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-4 text-sm text-white outline-none transition focus:border-[#7C3AED]"
                    placeholder="确认新密码"
                    autoComplete="new-password"
                  />
                  <div className="flex gap-2">
                    <button
                      className="flex-1 rounded-xl bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
                      type="button"
                      disabled={saving}
                      onClick={handleChangePassword}
                    >
                      {saving ? '提交中...' : '确认修改'}
                    </button>
                    <button
                      className="rounded-xl border border-[var(--border-soft)] px-4 py-3 text-sm text-[var(--text-muted)] transition hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                      type="button"
                      onClick={() => {
                        setShowPasswordForm(false)
                        setOldPassword('')
                        setNewPassword('')
                        setConfirmPassword('')
                        setError('')
                      }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-[28px] border border-red-500/20 bg-[rgba(40,14,22,0.68)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.16)]">
              <p className="m-0 text-sm font-medium text-white">会话管理</p>
              <p className="m-0 mt-2 text-xs leading-6 text-[var(--text-muted)]">
                退出登录后会清除当前浏览器中的登录状态。
              </p>
              <button
                className="mt-5 inline-flex items-center gap-2 rounded-xl border border-red-500/30 px-4 py-3 text-sm text-red-300 transition hover:bg-red-500/10"
                type="button"
                onClick={handleLogout}
              >
                <LogOut size={16} />
                退出登录
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
