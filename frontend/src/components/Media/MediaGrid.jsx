import { useState, useEffect, useRef } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import MediaCard from './MediaCard.jsx'
import { listAssets, uploadAsset, deleteAsset } from '../../services/asset.js'

// 格式化文件大小
function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 后端 type 数值映射为前端字符串
const typeMap = { 1: 'image', 2: 'video', 3: 'audio' }

// 将后端素材数据转换为 MediaCard 需要的格式
function mapAsset(item) {
  const type = typeMap[item.type] || 'image'
  const sizeStr = formatFileSize(item.file_size)
  const formatStr = item.format ? item.format.toUpperCase() : ''
  const durationStr = item.duration ? Math.round(item.duration) + 's' : ''
  // 组合 meta 信息：时长（如有）+ 文件大小 + 格式
  const metaParts = [durationStr, sizeStr, formatStr].filter(Boolean).join(' · ')
  return {
    id: item.id,
    name: item.title || '未命名素材',
    meta: metaParts,
    type,
    url: item.url,
  }
}

export default function MediaGrid() {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  // 加载素材列表
  const fetchAssets = async () => {
    try {
      setLoading(true)
      const res = await listAssets()
      const data = res.data ?? res
      const items = Array.isArray(data) ? data : data.items ?? data.results ?? []
      setAssets(items.map(mapAsset))
    } catch (err) {
      console.error('加载素材列表失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAssets()
  }, [])

  // 处理文件上传
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file)
      await uploadAsset(formData)
      // 上传成功后刷新列表
      await fetchAssets()
    } catch (err) {
      console.error('上传素材失败:', err)
    } finally {
      setUploading(false)
      // 清空 input 以便重复上传同名文件
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // 处理删除素材
  const handleDelete = async (assetId) => {
    try {
      await deleteAsset(assetId)
      // 删除成功后从列表中移除
      setAssets((prev) => prev.filter((a) => a.id !== assetId))
    } catch (err) {
      console.error('删除素材失败:', err)
    }
  }

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6">
        <h1 className="m-0 text-lg font-semibold">素材库</h1>
        <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
          管理视频、图片、音频素材，并在对话生成时快速引用。
        </p>
      </header>

      {/* 上传区域 */}
      <div
        className="mb-6 grid min-h-36 place-items-center rounded-xl border border-dashed border-[rgba(124,58,237,0.35)] bg-[rgba(26,26,46,0.65)] text-center hover:bg-[rgba(124,58,237,0.1)]"
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            fileInputRef.current?.click()
          }
        }}
      >
        <div>
          {uploading ? (
            <Loader2 className="mx-auto mb-3 animate-spin text-[#a78bfa]" size={24} />
          ) : (
            <Upload className="mx-auto mb-3 text-[#a78bfa]" size={24} />
          )}
          <p className="m-0 text-sm font-medium">
            {uploading ? '正在上传...' : '拖拽文件到此处开始上传'}
          </p>
          <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">支持视频、图片、音频格式</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*,image/*,audio/*"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* 加载状态 */}
      {loading ? (
        <div className="grid min-h-36 place-items-center text-sm text-[var(--text-muted)]">
          <Loader2 className="mr-2 animate-spin" size={18} />
          加载中...
        </div>
      ) : assets.length === 0 ? (
        /* 空状态 */
        <div className="grid min-h-36 place-items-center text-sm text-[var(--text-muted)]">
          暂无素材，点击上方区域上传。
        </div>
      ) : (
        /* 素材网格 */
        <div className="grid grid-cols-4 gap-3 max-[1280px]:grid-cols-3">
          {assets.map((item) => (
            <MediaCard key={item.id} item={item} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </section>
  )
}
