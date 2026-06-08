import { useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { listProducts } from '../../services/product.js'

/**
 * 商品选择弹窗
 * 搜索并选择一个商品，确认后回调 onConfirm(selectedProduct)。
 */
export default function ProductPickerModal({ open, selectedProduct, onClose, onConfirm }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [draftId, setDraftId] = useState(null)

  useEffect(() => {
    if (!open) return
    setDraftId(selectedProduct?.id ?? null)
    setKeyword('')
    setLoading(true)
    listProducts({ page: 1, page_size: 100 })
      .then((res) => setProducts(Array.isArray(res?.list) ? res.list : Array.isArray(res) ? res : []))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false))
  }, [open, selectedProduct])

  if (!open) return null

  const filtered = products.filter((p) => {
    if (!keyword.trim()) return true
    const q = keyword.toLowerCase()
    return (
      (p.name || '').toLowerCase().includes(q) ||
      (p.brand || '').toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q)
    )
  })

  function handleToggle(product) {
    setDraftId((prev) => (prev === product.id ? null : product.id))
  }

  function handleConfirm() {
    if (!draftId) {
      onConfirm(null)
      return
    }
    const product = products.find((p) => p.id === draftId)
    onConfirm(product || null)
  }

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="flex h-[min(680px,85vh)] w-full max-w-3xl flex-col rounded-[28px] border border-[var(--border-soft)] bg-[rgba(15,15,26,0.98)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-soft)] px-6 py-4">
          <div>
            <h2 className="m-0 text-lg font-semibold text-white">选择商品</h2>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
              选择一个商品关联到本次对话，商品信息会作为上下文传入
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

        {/* Search */}
        <div className="px-6 pt-4">
          <div className="flex items-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 py-2">
            <Search size={16} className="text-[var(--text-muted)]" />
            <input
              className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[var(--text-muted)]"
              placeholder="搜索商品名称、品牌..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
            {keyword ? (
              <button
                type="button"
                onClick={() => setKeyword('')}
                className="text-[var(--text-muted)] hover:text-white"
              >
                <X size={14} />
              </button>
            ) : null}
          </div>
        </div>

        {/* Grid */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="grid place-items-center py-20 text-sm text-[var(--text-muted)]">
              加载中...
            </div>
          ) : filtered.length === 0 ? (
            <div className="grid place-items-center py-20 text-sm text-[var(--text-muted)]">
              {keyword ? '没有匹配的商品' : '暂无商品，请先在商品管理中添加'}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((product) => {
                const selected = draftId === product.id
                return (
                  <button
                    key={product.id}
                    type="button"
                    onClick={() => handleToggle(product)}
                    className={`group relative overflow-hidden rounded-2xl border text-left transition ${
                      selected
                        ? 'border-[#a78bfa] shadow-[0_0_12px_rgba(167,139,250,0.25)]'
                        : 'border-[var(--border-soft)] hover:border-[rgba(167,139,250,0.4)]'
                    } bg-[rgba(255,255,255,0.03)]`}
                  >
                    {/* Image */}
                    <div className="relative h-36 overflow-hidden bg-[rgba(255,255,255,0.04)]">
                      {product.main_image_url ? (
                        <img
                          src={product.main_image_url}
                          alt={product.name}
                          className="h-full w-full object-cover transition group-hover:scale-105"
                        />
                      ) : (
                        <div className="grid h-full place-items-center text-2xl text-[var(--text-muted)]">
                          📦
                        </div>
                      )}
                      {selected && (
                        <div className="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-[#a78bfa] text-[11px] font-bold text-white">
                          ✓
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="p-3">
                      <p className="m-0 truncate text-sm font-medium text-white">
                        {product.name || '未命名商品'}
                      </p>
                      <div className="mt-1 flex items-center gap-2">
                        {product.brand ? (
                          <span className="rounded-md bg-[rgba(167,139,250,0.12)] px-1.5 py-0.5 text-[10px] text-[#a78bfa]">
                            {product.brand}
                          </span>
                        ) : null}
                        {product.price ? (
                          <span className="text-[11px] text-[#22c55e]">
                            ¥{product.price}
                          </span>
                        ) : null}
                      </div>
                      {product.description ? (
                        <p className="m-0 mt-1.5 line-clamp-2 text-[11px] leading-4 text-[var(--text-muted)]">
                          {product.description}
                        </p>
                      ) : null}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[var(--border-soft)] px-6 py-4">
          <p className="m-0 text-xs text-[var(--text-muted)]">
            {draftId ? '已选择 1 个商品（单选）' : '点击选择一个商品'}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.05)]"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              className="rounded-xl bg-[linear-gradient(135deg,#a78bfa_0%,#7c3aed_100%)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              添加到对话
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
