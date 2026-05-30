/** 工作流阶段配置 */
const STAGES = [
  { key: 'script', label: '剧本' },
  { key: 'image', label: '图片' },
  { key: 'video', label: '视频' },
]

/** 阶段顺序（用于判断是否已通过某阶段） */
const ORDER = ['created', 'script', 'image', 'video', 'completed']

/**
 * 获取指定阶段的状态标签文本
 * 根据项目当前所处阶段和状态，返回对应的中文状态描述。
 */
function statusLabel(stage, project) {
  if (!project) return '未开始'
  if (project.workflow_stage === 'completed') return '已完成'
  if (project.workflow_stage === stage) {
    return {
      idle: '待开始',
      running: '生成中',
      awaiting_review: '待确认',
      confirmed: '已确认',
      failed: '失败',
    }[project.stage_status] || project.stage_status
  }
  return ORDER.indexOf(project.workflow_stage) > ORDER.indexOf(stage) ? '已确认' : '未开始'
}

/** 三阶段进度条组件：显示剧本/图片/视频的完成状态 */
export default function StageProgress({ project }) {
  return (
    <div className="rounded-2xl border border-[rgba(148,163,184,0.14)] bg-[rgba(14,18,32,0.72)] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.18)]">
      <div className="flex items-center justify-between gap-3">
        {STAGES.map((stage, index) => {
          const current = project?.workflow_stage === stage.key
          const done = project?.workflow_stage === 'completed' || ORDER.indexOf(project?.workflow_stage) > ORDER.indexOf(stage.key)
          return (
            <div key={stage.key} className="flex flex-1 items-center">
              <div
                className={`flex min-w-0 flex-1 items-center gap-3 rounded-xl border px-4 py-3 ${
                  current
                    ? 'border-[#38bdf8]/40 bg-[#38bdf8]/10'
                    : done
                      ? 'border-[#10b981]/35 bg-[#10b981]/10'
                      : 'border-[rgba(148,163,184,0.12)] bg-[rgba(148,163,184,0.06)]'
                }`}
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/10 text-sm font-semibold">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <div className="font-medium text-white">{stage.label}</div>
                  <div className="text-xs text-[var(--text-muted)]">{statusLabel(stage.key, project)}</div>
                </div>
              </div>
              {index < STAGES.length - 1 && <div className="mx-2 h-px w-8 bg-[rgba(148,163,184,0.22)]" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
