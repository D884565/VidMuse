export default function UserProfile({ collapsed }) {
  return (
    <div className="flex items-center gap-3 rounded-lg px-2 py-2">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[rgba(124,58,237,0.24)] text-sm font-semibold">
        Z
      </div>
      <div className={`${collapsed ? 'hidden' : 'block'} min-w-0 max-[1024px]:hidden`}>
        <p className="m-0 truncate text-sm font-medium">创作者</p>
        <p className="m-0 truncate text-xs text-[var(--text-muted)]">Pro Workspace</p>
      </div>
    </div>
  )
}
