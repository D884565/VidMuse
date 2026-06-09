import { useEffect, useRef, useState } from 'react'
import { Loader2, RefreshCw, Trash2, X } from 'lucide-react'
import {
  deleteAsset,
  reuploadImageAsset,
  updateAsset,
  updateTextAsset,
} from '../../services/asset.js'

/**
 * 素材编辑弹窗
 * 支持编辑标题、文本内容，重新上传图片，以及删除素材。
 */
export default function AssetEditModal({ asset, onClose, onSaved, onDeleted }) {
  const [title, setTitle] = useState('')
  const [contentText, setContentText] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [imagePreview, setImagePreview] = useState('')
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (!asset) return
    setTitle(asset.name || '')
    setContentText(asset.content_text || '')
    setImagePreview(asset.url || '')
    setSaving(false)
    setUploading(false)
    setError('')
    setShowDeleteConfirm(false)
  }, [asset])

  if (!asset) return null

  async function handleSave() {
    try {
      setSaving(true)
      setError('')
      if (asset.type === 'text') {
        await updateTextAsset(asset.id, { title, content_text: contentText })
      } else {
        await updateAsset(asset.id, { title })
      }
      onSaved?.()
    } catch (err) {
      setError(err.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleReupload(event) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
      setError('请选择图片或视频文件')
      return
    }

    try {
      setUploading(true)
      setError('')
      const reader = new FileReader()
      reader.onload = (e) => setImagePreview(e.target.result)
      reader.readAsDataURL(file)

      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title || file.name)
      await reuploadImageAsset(asset.id, formData)
      onSaved?.()
    } catch (err) {
      setError(err.message || '图片重新上传失败')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDelete() {
    try {
      setSaving(true)
      await deleteAsset(asset.id)
      onDeleted?.(asset.id)
    } catch (err) {
      setError(err.message || '删除失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="flex h-[min(720px,90vh)] w-full max-w-3xl flex-col rounded-[28px] border border-[var(--border-soft)] bg-[rgba(15,15,26,0.98)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-soft)] px-6 py-4">
          <div>
            <h2 className="m-0 text-lg font-semibold text-white">
              {asset.type === 'text' ? '编辑文本素材' : asset.type === 'video' ? '编辑视频素材' : '编辑图片素材'}
            </h2>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
              ID: {asset.id} · {asset.type === 'text' ? '文本' : asset.type === 'video' ? '视频' : '图片'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-xl border border-[var(--border-soft)] text-[var(--text-muted)] transition hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="grid gap-6 sm:grid-cols-2">
            {/* Left: Preview */}
            <div>
              <span className="mb-2 block text-sm text-[var(--text-muted)]">素材预览</span>
              <div className="relative overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)]">
                {asset.type === 'image' ? (
                  imagePreview ? (
                    <img
                      src={imagePreview}
                      alt={title}
                      className="aspect-video w-full object-contain"
                    />
                  ) : (
                    <div className="flex aspect-video items-center justify-center text-[var(--text-muted)]">
                      无图片
                    </div>
                  )
                ) : asset.type === 'video' ? (
                  asset.url ? (
                    <video
                      src={asset.url}
                      controls
                      className="aspect-video w-full object-contain"
                    />
                  ) : (
                    <div className="flex aspect-video items-center justify-center text-[var(--text-muted)]">
                      无视频
                    </div>
                  )
                ) : (
                  <div className="max-h-64 overflow-y-auto p-4 text-sm leading-6 text-white/80">
                    {contentText || '（空文本）'}
                  </div>
                )}
                {uploading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                    <Loader2 className="animate-spin text-white" size={24} />
                  </div>
                )}
              </div>

              {(asset.type === 'image' || asset.type === 'video') && (
                <div className="mt-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={asset.type === 'video' ? 'video/*' : 'image/*'}
                    className="hidden"
                    onChange={handleReupload}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-2.5 text-sm text-white transition hover:bg-[rgba(255,255,255,0.08)] disabled:opacity-50"
                  >
                    <RefreshCw size={15} />
                    {uploading ? '上传中...' : asset.type === 'video' ? '重新上传视频' : '重新上传图片'}
                  </button>
                </div>
              )}
            </div>

            {/* Right: Form */}
            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm text-[var(--text-muted)]">素材名称</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#a78bfa]"
                  placeholder="输入素材名称"
                />
              </div>

              {asset.type === 'text' && (
                <div>
                  <label className="mb-2 block text-sm text-[var(--text-muted)]">文本内容</label>
                  <textarea
                    value={contentText}
                    onChange={(e) => setContentText(e.target.value)}
                    rows={8}
                    className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#a78bfa]"
                    placeholder="输入文本内容"
                  />
                </div>
              )}

              <div className="rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.02)] p-3 text-xs text-[var(--text-muted)]">
                {asset.type === 'text' ? '修改文本内容后会立即更新素材记录。' : asset.type === 'video' ? '更换视频后，所有引用该素材的地方都会使用新视频。' : '更换图片后，所有引用该素材的地方都会使用新图片。'}
              </div>

              {error && (
                <p className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {error}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[var(--border-soft)] px-6 py-4">
          <div>
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-400">确定删除？</span>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={saving}
                  className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/30 disabled:opacity-50"
                >
                  {saving ? '删除中...' : '确认删除'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  className="rounded-lg px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-white"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-red-400 transition hover:bg-red-500/10 hover:text-red-300"
              >
                <Trash2 size={15} />
                删除素材
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.05)]"
              disabled={saving}
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || uploading}
              className="rounded-xl bg-[linear-gradient(135deg,#a78bfa_0%,#7c3aed_100%)] px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
