import { useEffect, useMemo, useState } from 'react'
import { Package, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'
import ConfirmDialog from '../Common/ConfirmDialog.jsx'
import ProductFormModal from './ProductFormModal.jsx'
import { filterOwnedProducts } from './productFormUtils.js'
import { createProduct, deleteProduct, listProducts, updateProduct } from '../../services/product.js'

function formatPrice(price) {
  if (price == null || price === '') return '未填写价格'
  return `¥${Number(price).toFixed(2)}`
}

function ProductCard({ product, onEdit, onDelete }) {
  return (
    <article className="overflow-hidden rounded-[24px] border border-[var(--border-soft)] bg-[rgba(26,26,46,0.72)] transition hover:-translate-y-0.5 hover:border-[rgba(56,189,248,0.35)] hover:shadow-[0_10px_32px_rgba(56,189,248,0.10)]">
      <div className="grid aspect-[16/10] place-items-center overflow-hidden bg-[rgba(255,255,255,0.04)]">
        {product.main_image_url ? (
          <img src={product.main_image_url} alt={product.name} className="h-full w-full object-cover" />
        ) : (
          <div className="grid h-full w-full place-items-center bg-[linear-gradient(135deg,rgba(56,189,248,0.14),rgba(34,197,94,0.10))] text-[var(--text-muted)]">
            <Package size={28} />
          </div>
        )}
      </div>

      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="m-0 truncate text-base font-semibold text-white">{product.name}</h3>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
              {product.brand || '未填写品牌'}
            </p>
          </div>
          <span className="rounded-full bg-[rgba(56,189,248,0.12)] px-2.5 py-1 text-xs font-medium text-[#7dd3fc]">
            {formatPrice(product.price)}
          </span>
        </div>

        <p className="m-0 line-clamp-3 min-h-[60px] text-sm leading-6 text-[var(--text-muted)]">
          {product.description || '还没有补充商品描述。'}
        </p>

        <div className="flex items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
          <span>创建于 {product.created_at || '--'}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
              onClick={() => onEdit(product)}
            >
              <Pencil size={14} />
              编辑
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-red-300 hover:bg-red-500/10 hover:text-red-200"
              onClick={() => onDelete(product)}
            >
              <Trash2 size={14} />
              删除
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}

export default function ProductManager() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState({ open: false, productId: null, name: '' })

  async function fetchProducts() {
    setLoading(true)
    setError('')
    try {
      const data = await listProducts({ page: 1, page_size: 100 })
      const items = Array.isArray(data?.list) ? data.list : Array.isArray(data) ? data : []
      setProducts(filterOwnedProducts(items))
    } catch (fetchError) {
      setError(fetchError.message || '加载商品失败')
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    queueMicrotask(fetchProducts)
  }, [])

  const isEmpty = useMemo(
    () => !loading && products.length === 0,
    [loading, products]
  )

  function openCreateModal() {
    setEditingProduct(null)
    setModalOpen(true)
  }

  function openEditModal(product) {
    setEditingProduct(product)
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditingProduct(null)
  }

  async function handleSubmitProduct(payload, currentProduct) {
    if (currentProduct) await updateProduct(currentProduct.id, payload)
    else await createProduct(payload)
    closeModal()
    await fetchProducts()
  }

  return (
    <section className="min-h-screen px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="m-0 text-2xl font-semibold text-white">我的商品</h1>
            <p className="m-0 mt-2 text-sm text-[var(--text-muted)]">
              这里展示当前账号拥有的商品。第一版先支持最小字段维护，后续再扩展分类、素材和解析能力。
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-2.5 text-sm text-white hover:bg-[rgba(255,255,255,0.08)]"
              onClick={fetchProducts}
            >
              <RefreshCw size={16} />
              刷新
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl bg-[linear-gradient(135deg,#38bdf8_0%,#22c55e_100%)] px-4 py-2.5 text-sm font-medium text-[#07131f]"
              onClick={openCreateModal}
            >
              <Plus size={16} />
              新增商品
            </button>
          </div>
        </header>

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="grid min-h-[320px] place-items-center rounded-[28px] border border-[var(--border-soft)] bg-[rgba(255,255,255,0.03)] text-sm text-[var(--text-muted)]">
            正在加载商品...
          </div>
        ) : null}

        {isEmpty ? (
          <div className="grid min-h-[320px] place-items-center rounded-[28px] border border-[var(--border-soft)] bg-[rgba(255,255,255,0.03)]">
            <div className="text-center">
              <h3 className="m-0 text-lg font-semibold text-white">还没有商品</h3>
              <p className="mt-2 text-sm text-[var(--text-muted)]">
                先添加一个商品，后面就可以继续扩展素材和生成链路。
              </p>
              <button
                type="button"
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[linear-gradient(135deg,#38bdf8_0%,#22c55e_100%)] px-4 py-2.5 text-sm font-medium text-[#07131f]"
                onClick={openCreateModal}
              >
                <Plus size={16} />
                新增商品
              </button>
            </div>
          </div>
        ) : null}

        {!loading && products.length > 0 ? (
          <div className="grid grid-cols-3 gap-5 max-[1280px]:grid-cols-2 max-[760px]:grid-cols-1">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onEdit={openEditModal}
                onDelete={(item) => setConfirmDelete({ open: true, productId: item.id, name: item.name })}
              />
            ))}
          </div>
        ) : null}
      </div>

      <ProductFormModal
        open={modalOpen}
        mode={editingProduct ? 'edit' : 'create'}
        initialProduct={editingProduct}
        onClose={closeModal}
        onSubmit={handleSubmitProduct}
      />

      <ConfirmDialog
        open={confirmDelete.open}
        title="删除商品"
        message={`确定要删除“${confirmDelete.name || '该商品'}”吗？此操作不可撤销。`}
        onCancel={() => setConfirmDelete({ open: false, productId: null, name: '' })}
        onConfirm={async () => {
          const productId = confirmDelete.productId
          setConfirmDelete({ open: false, productId: null, name: '' })
          if (productId) {
            await deleteProduct(productId)
            await fetchProducts()
          }
        }}
      />
    </section>
  )
}
