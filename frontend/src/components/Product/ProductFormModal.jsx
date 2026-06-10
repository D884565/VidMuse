import { useMemo, useRef, useState } from 'react'
import { normalizeProductPayload } from './productFormUtils.js'
import { uploadAsset } from '../../services/asset.js'

const EMPTY_FORM = {
  name: '',
  brand: '',
  price: '',
  main_image_url: '',
  description: '',
}

function buildFormState(product) {
  if (!product) return EMPTY_FORM
  return {
    name: product.name || '',
    brand: product.brand || '',
    price: product.price == null ? '' : String(product.price),
    main_image_url: product.main_image_url || '',
    description: product.description || '',
  }
}

export default function ProductFormModal({
  open,
  mode,
  initialProduct,
  onClose,
  onSubmit,
}) {
  const formKey = `${open ? 'open' : 'closed'}:${initialProduct?.id || 'new'}:${mode || 'create'}`
  return <ProductFormModalContent key={formKey} open={open} mode={mode} initialProduct={initialProduct} onClose={onClose} onSubmit={onSubmit} />
}

function ProductFormModalContent({
  open,
  mode,
  initialProduct,
  onClose,
  onSubmit,
}) {
  const [form, setForm] = useState(() => buildFormState(initialProduct))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [imagePreview, setImagePreview] = useState(() => form.main_image_url || '')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const title = useMemo(
    () => (mode === 'edit' ? '编辑商品' : '新增商品'),
    [mode]
  )

  if (!open) return null

  function patchField(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function handleFileSelect(event) {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      setError('请选择图片文件')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('图片大小不能超过 10MB')
      return
    }

    const reader = new FileReader()
    reader.onload = (e) => setImagePreview(e.target.result)
    reader.readAsDataURL(file)

    try {
      setUploading(true)
      setError('')
      const formData = new FormData()
      formData.append('file', file)
      formData.append('type', '1')
      const result = await uploadAsset(formData)
      patchField('main_image_url', result.url)
    } catch (uploadError) {
      setError(uploadError.message || '图片上传失败')
      setImagePreview('')
    } finally {
      setUploading(false)
    }
  }

  function handleRemoveImage() {
    setImagePreview('')
    patchField('main_image_url', '')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const payload = normalizeProductPayload(form)

    if (!payload.name) {
      setError('商品名称不能为空')
      return
    }
    if (form.price.trim() && Number.isNaN(payload.price)) {
      setError('价格必须是合法数字')
      return
    }

    try {
      setSubmitting(true)
      setError('')
      await onSubmit(payload, initialProduct || null)
    } catch (submitError) {
      setError(submitError.message || '保存商品失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-[28px] border border-[var(--border-soft)] bg-[rgba(15,15,26,0.98)] p-6 shadow-2xl">
        <div className="mb-5">
          <h2 className="m-0 text-lg font-semibold text-white">{title}</h2>
          <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
            维护商品基础信息，后续可用于素材和视频生成链路。
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm text-[var(--text-muted)]">商品名称</span>
              <input
                value={form.name}
                onChange={(event) => patchField('name', event.target.value)}
                className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#38bdf8]"
                placeholder="请输入商品名称"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm text-[var(--text-muted)]">品牌</span>
              <input
                value={form.brand}
                onChange={(event) => patchField('brand', event.target.value)}
                className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#38bdf8]"
                placeholder="请输入品牌"
              />
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm text-[var(--text-muted)]">价格</span>
              <input
                value={form.price}
                onChange={(event) => patchField('price', event.target.value)}
                className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#38bdf8]"
                placeholder="例如 99.9"
              />
            </label>
            <div className="block">
              <span className="mb-2 block text-sm text-[var(--text-muted)]">商品主图</span>
              {imagePreview ? (
                <div className="relative">
                  <img
                    src={imagePreview}
                    alt="商品主图"
                    className="h-32 w-full rounded-xl border border-[var(--border-soft)] object-cover"
                  />
                  <button
                    type="button"
                    onClick={handleRemoveImage}
                    className="absolute right-2 top-2 rounded-full bg-red-500/80 px-2 py-1 text-xs text-white hover:bg-red-500"
                  >
                    删除
                  </button>
                  {uploading && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/50">
                      <span className="text-sm text-white">上传中...</span>
                    </div>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] hover:border-[#38bdf8] hover:bg-[rgba(56,189,248,0.05)]"
                >
                  <svg className="mb-2 h-8 w-8 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <span className="text-sm text-[var(--text-muted)]">
                    {uploading ? '上传中...' : '点击上传图片'}
                  </span>
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>
          </div>

          <label className="block">
            <span className="mb-2 block text-sm text-[var(--text-muted)]">商品描述</span>
            <textarea
              value={form.description}
              onChange={(event) => patchField('description', event.target.value)}
              rows={6}
              className="w-full rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-white outline-none focus:border-[#38bdf8]"
              placeholder="补充这个商品的核心卖点、适用场景或一句话说明"
            />
          </label>

          {error ? (
            <p className="m-0 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              className="rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.05)]"
              onClick={onClose}
              disabled={submitting}
            >
              取消
            </button>
            <button
              type="submit"
              className="rounded-xl bg-[linear-gradient(135deg,#38bdf8_0%,#22c55e_100%)] px-4 py-2 text-sm font-medium text-[#07131f] disabled:opacity-60"
              disabled={submitting}
            >
              {submitting ? '保存中...' : '保存商品'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
