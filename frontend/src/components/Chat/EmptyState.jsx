import { Clapperboard, Megaphone, Smartphone } from 'lucide-react'

const prompts = [
  { icon: Megaphone, label: '生成产品宣传片' },
  { icon: Smartphone, label: '制作短视频' },
  { icon: Clapperboard, label: '创建分镜脚本' },
]

export default function EmptyState() {
  return (
    <div className="grid min-h-[420px] place-items-center text-center">
      <div>
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)]">
          <Clapperboard size={26} />
        </div>
        <h2 className="text-xl font-semibold">今天想创作什么视频？</h2>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {prompts.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.label}
                className="flex items-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.72)] px-4 py-3 text-sm text-[var(--text-muted)] hover:border-[rgba(124,58,237,0.45)] hover:text-white"
                type="button"
              >
                <Icon size={16} />
                {item.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
