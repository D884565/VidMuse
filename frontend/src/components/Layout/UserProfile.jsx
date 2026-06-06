import { useAppStore } from '../../store/appStore.js'

export default function UserProfile({ collapsed }) {
  const user = useAppStore((state) => state.user)
  const initial = user?.username?.[0]?.toUpperCase() || 'U'
  const username = user?.username || '未登录'

  return (
    <>
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,rgba(124,58,237,0.9)_0%,rgba(168,85,247,0.9)_100%)] text-sm font-semibold text-white shadow-[0_8px_24px_rgba(124,58,237,0.22)]">
        {initial}
      </div>
      <div className={`${collapsed ? 'hidden' : 'block'} min-w-0 max-[1024px]:hidden`}>
        <p className="m-0 truncate text-sm font-medium text-white">{username}</p>
        <p className="m-0 truncate text-xs text-[var(--text-muted)]">账户中心</p>
      </div>
    </>
  )
}
