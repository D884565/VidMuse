import { Check, Loader2, Search, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { listAssets } from '../../services/asset.js'
import { formatSelectedAssetLabel, getAssetTypeLabel } from './materialPrompt.js'

const TYPE_MAP = {
  1: 'image',
  2: 'video',
  3: 'audio',
  4: 'text',
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(duration) {
  if (!duration) return ''
  return `${Math.round(duration)}s`
}

function mapAsset(item) {
  const type = TYPE_MAP[item.type]
  if (!type || !item?.id) return null

  return {
    id: item.id,
    type,
    title: item.title || '',
    url: item.url || '',
    contentText: item.content_text || '',
    format: item.format || '',
    meta: [formatFileSize(item.file_size), formatDuration(item.duration), item.format?.toUpperCase()]
      .filter(Boolean)
      .join(' · '),
  }
}

function renderPreview(asset) {
  if (asset.type === 'image' && asset.url) {
    return (
      <img
        src={asset.url}
        alt={formatSelectedAssetLabel(asset)}
        className="h-full w-full object-cover"
      />
    )
  }

  if (asset.type === 'text') {
    return (
      <div className="line-clamp-4 px-4 py-3 text-xs leading-5 text-[var(--text-muted)]">
        {asset.contentText || '文本素材'}
      </div>
    )
  }

  return (
    <div className="grid h-full place-items-center text-sm font-medium text-[var(--text-muted)]">
      {getAssetTypeLabel(asset.type)}
    </div>
  )
}

export default function MaterialPickerModal({
  open,
  selectedAssets,
  onClose,
  onConfirm,
}) {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [draftIds, setDraftIds] = useState([])

  useEffect(() => {
    if (!open) return
    setDraftIds((selectedAssets || []).map((asset) => asset.id))
  }, [open, selectedAssets])

  useEffect(() => {
    if (!open) return

    let cancelled = false
    async function fetchAssets() {
      setLoading(true)
      try {
        const data = await listAssets({ page: 1, page_size: 120 })
        if (cancelled) return
        const items = data?.list ?? (Array.isArray(data) ? data : [])
        setAssets(items.map(mapAsset).filter(Boolean))
      } catch (error) {
        if (!cancelled) {
          console.error('加载素材库失败:', error)
          setAssets([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchAssets()
    return () => {
      cancelled = true
    }
  }, [open])

  const filteredAssets = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase()
    return assets.filter((asset) => {
      const matchesType = typeFilter === 'all' || asset.type === typeFilter
      const matchesKeyword = !normalizedKeyword
        || formatSelectedAssetLabel(asset).toLowerCase().includes(normalizedKeyword)
        || asset.contentText.toLowerCase().includes(normalizedKeyword)
      return matchesType && matchesKeyword
    })
  }, [assets, keyword, typeFilter])

  if (!open) return null

  function toggleAsset(assetId) {
    setDraftIds((current) => (
      current.includes(assetId)
        ? current.filter((id) => id !== assetId)
        : [...current, assetId]
    ))
  }

  function handleConfirm() {
    const selected = assets.filter((asset) => draftIds.includes(asset.id))
    onConfirm(selected)
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[rgba(3,7,18,0.72)] px-4 py-6 backdrop-blur-sm">
      <div className="flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-[var(--border-soft)] bg-[rgba(15,15,26,0.98)] shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
        <div className="flex items-center justify-between border-b border-[var(--border-soft)] px-6 py-5">
          <div>
            <h2 className="m-0 text-lg font-semibold text-white">素材库</h2>
            <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
              选择一个或多个素材，作为当前对话的参考依据
            </p>
          </div>
          <button
            type="button"
            className="rounded-xl p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
            onClick={onClose}
            aria-label="关闭素材库"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-wrap gap-3 border-b border-[var(--border-soft)] px-6 py-4">
          <label className="flex min-w-[260px] flex-1 items-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 py-2.5 text-sm text-[var(--text-muted)]">
            <Search size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="w-full bg-transparent text-white outline-none placeholder:text-[var(--text-muted)]"
              placeholder="搜索素材标题或文本内容"
            />
          </label>

          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            className="rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 py-2.5 text-sm text-white outline-none"
          >
            <option value="all">全部类型</option>
            <option value="image">图片</option>
            <option value="video">视频</option>
            <option value="audio">音频</option>
            <option value="text">文本</option>
          </select>
        </div>

        <div className="min-h-[360px] flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="grid min-h-[280px] place-items-center text-sm text-[var(--text-muted)]">
              <span className="inline-flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                正在加载素材...
              </span>
            </div>
          ) : filteredAssets.length === 0 ? (
            <div className="grid min-h-[280px] place-items-center text-sm text-[var(--text-muted)]">
              当前没有可选素材
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-4 max-[1280px]:grid-cols-3 max-[900px]:grid-cols-2 max-[640px]:grid-cols-1">
              {filteredAssets.map((asset) => {
                const selected = draftIds.includes(asset.id)
                return (
                  <button
                    key={asset.id}
                    type="button"
                    onClick={() => toggleAsset(asset.id)}
                    className={`group relative overflow-hidden rounded-2xl border text-left transition ${
                      selected
                        ? 'border-[#38bdf8] bg-[rgba(56,189,248,0.08)] shadow-[0_8px_24px_rgba(56,189,248,0.14)]'
                        : 'border-[var(--border-soft)] bg-[rgba(255,255,255,0.03)] hover:border-[rgba(56,189,248,0.4)] hover:bg-[rgba(255,255,255,0.05)]'
                    }`}
                  >
                    <span
                      className={`absolute right-3 top-3 z-10 grid h-7 w-7 place-items-center rounded-full border-2 transition ${
                        selected
                          ? 'border-[#38bdf8] bg-[#38bdf8] text-[#04121f]'
                          : 'border-white/80 bg-[rgba(15,23,42,0.75)] text-transparent'
                      }`}
                    >
                      <Check size={14} strokeWidth={3} />
                    </span>
                    <div className="grid aspect-video overflow-hidden bg-[rgba(255,255,255,0.04)]">
                      {renderPreview(asset)}
                    </div>
                    <div className="space-y-2 p-3">
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-[rgba(255,255,255,0.06)] px-2 py-1 text-[11px] text-[var(--text-muted)]">
                          {getAssetTypeLabel(asset.type)}
                        </span>
                        {asset.meta ? (
                          <span className="truncate text-[11px] text-[var(--text-muted)]">{asset.meta}</span>
                        ) : null}
                      </div>
                      <p className="m-0 truncate text-sm font-medium text-white">
                        {formatSelectedAssetLabel(asset)}
                      </p>
                      {asset.type === 'text' && asset.contentText ? (
                        <p className="m-0 line-clamp-2 text-xs leading-5 text-[var(--text-muted)]">
                          {asset.contentText}
                        </p>
                      ) : null}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-[var(--border-soft)] px-6 py-4">
          <p className="m-0 text-sm text-[var(--text-muted)]">
            已选择 {draftIds.length} 个素材，发送时会作为参考素材写入提示词
          </p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
              onClick={onClose}
            >
              取消
            </button>
            <button
              type="button"
              className="rounded-xl bg-[linear-gradient(135deg,#38bdf8_0%,#22c55e_100%)] px-4 py-2 text-sm font-medium text-[#07131f]"
              onClick={handleConfirm}
            >
              添加到对话
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
