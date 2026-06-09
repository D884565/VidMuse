import { useEffect, useRef, useState } from 'react'
import { Loader2, Plus } from 'lucide-react'
import ConfirmDialog from '../Common/ConfirmDialog.jsx'
import MediaCard from './MediaCard.jsx'
import AssetEditModal from './AssetEditModal.jsx'

/* 素材库页面 — 管理图片、视频、文本等素材资源 */
import {
  deleteAsset,
  listAssets,
  uploadAsset,
} from '../../services/asset.js'

const typeMap = { 1: 'image', 2: 'video', 4: 'text' }

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getAssetTypeLabel(type) {
  return {
    image: '图片',
    video: '视频',
    text: '文本',
  }[type] || '素材'
}

function mapAsset(item) {
  const type = typeMap[item.type]
  if (!type) return null

  const sizeStr = formatFileSize(item.file_size)
  const formatStr = item.format ? item.format.toUpperCase() : ''
  const metaParts = [getAssetTypeLabel(type), sizeStr, formatStr].filter(Boolean).join(' · ')

  return {
    id: item.id,
    name: item.title || '未命名素材',
    meta: metaParts,
    type,
    url: item.url,
    content_text: item.content_text || '',
  }
}

export default function MediaGrid() {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const [confirmDelete, setConfirmDelete] = useState({ open: false, assetId: null, title: '' })
  const [editAsset, setEditAsset] = useState(null)
  const fileInputRef = useRef(null)

  const filteredAssets =
    activeTab === 'all' ? assets : assets.filter((asset) => asset.type === activeTab)

  const fetchAssets = async () => {
    try {
      setLoading(true)
      const data = await listAssets({ page: 1, page_size: 100 })
      const items = data?.list ?? (Array.isArray(data) ? data : [])
      setAssets(items.map(mapAsset).filter(Boolean))
    } catch (err) {
      console.error('加载素材列表失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    queueMicrotask(fetchAssets)
  }, [])

  const resetUploadInput = (ref) => {
    if (ref.current) ref.current.value = ''
  }

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file)
      formData.append('type', file.type.startsWith('video/') ? '2' : '1')
      formData.append('title', file.name)
      await uploadAsset(formData)
      await fetchAssets()
    } catch (err) {
      console.error('上传素材失败:', err)
      alert('上传失败，请重试。')
    } finally {
      setUploading(false)
      resetUploadInput(fileInputRef)
    }
  }

  const handleDelete = async (assetId) => {
    try {
      await deleteAsset(assetId)
      setAssets((prev) => prev.filter((asset) => asset.id !== assetId))
      if (editAsset?.id === assetId) setEditAsset(null)
    } catch (err) {
      console.error('删除素材失败:', err)
      alert('删除失败，请重试。')
    }
  }

  const handleCardClick = (item) => {
    setEditAsset(item)
  }

  const handleEditSaved = async () => {
    await fetchAssets()
    setEditAsset(null)
  }

  const handleEditDeleted = (assetId) => {
    setEditAsset(null)
    setAssets((prev) => prev.filter((asset) => asset.id !== assetId))
  }

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">素材库</h1>
          <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
            点击素材卡片可编辑名称、重新上传或修改文本内容。
          </p>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2.5 rounded-xl bg-[#7c3aed] px-6 py-3 text-base font-medium text-white shadow-lg shadow-[#7c3aed]/25 hover:bg-[#6d28d9]"
          onClick={() => fileInputRef.current?.click()}
        >
          <Plus size={20} />
          新增素材
        </button>
      </header>

      <div className="mb-6 flex flex-wrap gap-2">
        {['all', 'image', 'video', 'text'].map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-full px-4 py-2 text-sm transition ${
              activeTab === tab
                ? 'bg-[#7c3aed] text-white'
                : 'border border-[var(--border-soft)] bg-[rgba(255,255,255,0.03)] text-[var(--text-muted)] hover:text-white'
            }`}
          >
            {tab === 'all' ? '全部' : getAssetTypeLabel(tab)}
          </button>
        ))}
      </div>

      <div className="mb-6 flex min-h-16 items-center justify-between rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.5)] px-4 py-3">
        <div>
          <p className="m-0 text-sm font-medium text-white">
            {uploading ? '正在上传...' : '通过"新增素材"添加图片或视频素材'}
          </p>
          <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
            图片和视频会直接上传到素材库，并作为新的素材记录展示。
          </p>
        </div>
        {uploading ? <Loader2 className="animate-spin text-[#a78bfa]" size={18} /> : null}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,video/*"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {loading ? (
        <div className="grid min-h-36 place-items-center text-sm text-[var(--text-muted)]">
          <Loader2 className="mr-2 animate-spin" size={18} />
          正在加载素材...
        </div>
      ) : filteredAssets.length === 0 ? (
        <div className="grid min-h-36 place-items-center text-sm text-[var(--text-muted)]">
          当前分类下还没有素材。
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-3 max-[1280px]:grid-cols-3 max-[880px]:grid-cols-2 max-[560px]:grid-cols-1">
          {filteredAssets.map((item) => (
            <MediaCard
              key={item.id}
              item={item}
              onClick={handleCardClick}
              onDelete={(assetId) => setConfirmDelete({ open: true, assetId, title: item.name })}
            />
          ))}
        </div>
      )}

      {/* Asset edit modal (new, click-to-edit) */}
      <AssetEditModal
        asset={editAsset}
        onClose={() => setEditAsset(null)}
        onSaved={handleEditSaved}
        onDeleted={handleEditDeleted}
      />

      <ConfirmDialog
        open={confirmDelete.open}
        title="删除素材"
        message={`确定要删除"${confirmDelete.title || '该素材'}"吗？此操作不可撤销。`}
        onCancel={() => setConfirmDelete({ open: false, assetId: null, title: '' })}
        onConfirm={async () => {
          const assetId = confirmDelete.assetId
          setConfirmDelete({ open: false, assetId: null, title: '' })
          if (assetId) {
            await handleDelete(assetId)
          }
        }}
      />
    </section>
  )
}
