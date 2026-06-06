import { Package, Plus, Send, SlidersHorizontal, X, Image as ImageIcon, Upload, FileText, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import MaterialPickerModal from './MaterialPickerModal.jsx'
import ProductPickerModal from './ProductPickerModal.jsx'
import ParameterPanel from '../Parameters/ParameterPanel.jsx'
import { formatSelectedAssetLabel, getAssetTypeLabel } from './materialPrompt.js'
import { analyzeChatReference } from '../../services/chat.js'

function SelectedAssetChip({ asset, onRemove }) {
  const isImage = asset.type === 'image' && asset.url

  return (
    <div className="relative w-[72px] shrink-0">
      <div className="relative h-[72px] overflow-hidden rounded-2xl border border-[rgba(56,189,248,0.25)] bg-[rgba(255,255,255,0.05)]">
        {isImage ? (
          <img
            src={asset.url}
            alt={formatSelectedAssetLabel(asset)}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full place-items-center bg-[linear-gradient(135deg,rgba(56,189,248,0.16),rgba(34,197,94,0.12))] text-xs font-medium text-white">
            {getAssetTypeLabel(asset.type)}
          </div>
        )}
        <button
          type="button"
          onClick={() => onRemove(asset.id)}
          className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-full border border-white/15 bg-[rgba(15,23,42,0.86)] text-white transition hover:bg-[rgba(15,23,42,1)]"
          aria-label={`移除素材 ${formatSelectedAssetLabel(asset)}`}
        >
          <X size={12} />
        </button>
      </div>
      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">
        {formatSelectedAssetLabel(asset)}
      </p>
    </div>
  )
}

function SelectedProductChip({ product, onRemove }) {
  return (
    <div className="relative w-[72px] shrink-0">
      <div className="relative h-[72px] overflow-hidden rounded-2xl border border-[rgba(167,139,250,0.35)] bg-[rgba(167,139,250,0.08)]">
        {product.main_image_url ? (
          <img
            src={product.main_image_url}
            alt={product.name}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full place-items-center bg-[linear-gradient(135deg,rgba(167,139,250,0.16),rgba(124,58,237,0.12))] text-xs font-medium text-white">
            <Package size={20} />
          </div>
        )}
        <button
          type="button"
          onClick={onRemove}
          className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-full border border-white/15 bg-[rgba(15,23,42,0.86)] text-white transition hover:bg-[rgba(15,23,42,1)]"
          aria-label={`移除商品 ${product.name}`}
        >
          <X size={12} />
        </button>
        <span className="absolute bottom-0 left-0 right-0 bg-[rgba(167,139,250,0.2)] px-1 py-0.5 text-center text-[9px] font-medium text-[#a78bfa]">
          商品
        </span>
      </div>
      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">
        {product.name}
      </p>
    </div>
  )
}

function LocalRefChip({ localRef, onRemove }) {
  const refItem = localRef
  const isImage = refItem.type === 'image'
  const isAnalyzing = refItem.analyzing

  return (
    <div className="relative w-[72px] shrink-0">
      <div className="relative h-[72px] overflow-hidden rounded-2xl border border-[rgba(34,197,94,0.35)] bg-[rgba(34,197,94,0.08)]">
        {isImage && refItem.previewUrl ? (
          <img
            src={refItem.previewUrl}
            alt={refItem.title}
            className="h-full w-full object-cover"
          />
        ) : isImage ? (
          <div className="grid h-full place-items-center bg-[linear-gradient(135deg,rgba(34,197,94,0.16),rgba(16,185,129,0.12))] text-xs font-medium text-white">
            <ImageIcon size={20} />
          </div>
        ) : (
          <div className="grid h-full place-items-center bg-[linear-gradient(135deg,rgba(34,197,94,0.16),rgba(16,185,129,0.12))]">
            <FileText size={20} className="text-[#22c55e]" />
          </div>
        )}
        {isAnalyzing && (
          <div className="absolute inset-0 flex items-center justify-center bg-[rgba(15,23,42,0.7)]">
            <Loader2 size={18} className="animate-spin text-[#22c55e]" />
          </div>
        )}
        <button
          type="button"
          onClick={() => onRemove(refItem.id)}
          className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-full border border-white/15 bg-[rgba(15,23,42,0.86)] text-white transition hover:bg-[rgba(15,23,42,1)]"
          aria-label={`移除参考 ${refItem.title}`}
        >
          <X size={12} />
        </button>
        <span className="absolute bottom-0 left-0 right-0 bg-[rgba(34,197,94,0.2)] px-1 py-0.5 text-center text-[9px] font-medium text-[#22c55e]">
          参考
        </span>
      </div>
      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">
        {refItem.title}
      </p>
    </div>
  )
}

function PlusMenu({ onSelect, onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 mb-2 w-48 overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(22,22,40,0.98)] py-1 shadow-2xl backdrop-blur-xl"
    >
      <button
        type="button"
        onClick={() => onSelect('material')}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-[var(--text-muted)] transition hover:bg-[rgba(56,189,248,0.1)] hover:text-white"
      >
        <ImageIcon size={16} className="text-[#38bdf8]" />
        素材库
      </button>
      <button
        type="button"
        onClick={() => onSelect('product')}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-[var(--text-muted)] transition hover:bg-[rgba(167,139,250,0.1)] hover:text-white"
      >
        <Package size={16} className="text-[#a78bfa]" />
        商品
      </button>
      <div className="my-1 border-t border-[var(--border-soft)]" />
      <button
        type="button"
        onClick={() => onSelect('local-image')}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-[var(--text-muted)] transition hover:bg-[rgba(34,197,94,0.1)] hover:text-white"
      >
        <Upload size={16} className="text-[#22c55e]" />
        上传图片
      </button>
      <button
        type="button"
        onClick={() => onSelect('local-text')}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-[var(--text-muted)] transition hover:bg-[rgba(34,197,94,0.1)] hover:text-white"
      >
        <FileText size={16} className="text-[#22c55e]" />
        粘贴文本
      </button>
    </div>
  )
}

export default function SmartInput({ onSend }) {
  const [value, setValue] = useState('')
  const [panelOpen, setPanelOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [productPickerOpen, setProductPickerOpen] = useState(false)
  const [selectedAssets, setSelectedAssets] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [localRefs, setLocalRefs] = useState([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [textInputOpen, setTextInputOpen] = useState(false)
  const [textDraft, setTextDraft] = useState('')
  const fileInputRef = useRef(null)

  const canSend = value.trim().length > 0
  const selectedAssetIds = useMemo(
    () => new Set(selectedAssets.map((asset) => asset.id)),
    [selectedAssets]
  )

  function submit(event) {
    event.preventDefault()
    if (!canSend) return
    // 只传已完成分析的 refs
    const readyRefs = localRefs.filter((r) => !r.analyzing)
    onSend({
      content: value,
      selectedAssets,
      selectedProduct,
      localRefs: readyRefs,
    })
    setValue('')
    setSelectedAssets([])
    setSelectedProduct(null)
    setLocalRefs([])
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      submit(event)
    }
  }

  function handleConfirmAssets(assets) {
    setSelectedAssets(assets)
    setPickerOpen(false)
  }

  function handleConfirmProduct(product) {
    setSelectedProduct(product)
    setProductPickerOpen(false)
  }

  function handleRemoveAsset(assetId) {
    setSelectedAssets((current) => current.filter((asset) => asset.id !== assetId))
  }

  function handleRemoveProduct() {
    setSelectedProduct(null)
  }

  function handlePlusMenuSelect(type) {
    setMenuOpen(false)
    if (type === 'material') {
      setPickerOpen(true)
    } else if (type === 'product') {
      setProductPickerOpen(true)
    } else if (type === 'local-image') {
      fileInputRef.current?.click()
    } else if (type === 'local-text') {
      setTextInputOpen(true)
      setTextDraft('')
    }
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (!file) return
    // 重置 input 以便同一文件可再次选择
    event.target.value = ''

    const refId = crypto.randomUUID()
    const previewUrl = URL.createObjectURL(file)

    // 先加入一个 analyzing 状态的 ref
    setLocalRefs((prev) => [
      ...prev,
      {
        id: refId,
        type: 'image',
        title: file.name,
        previewUrl,
        url: '',
        features: null,
        analyzing: true,
      },
    ])

    try {
      const result = await analyzeChatReference(file)
      setLocalRefs((prev) =>
        prev.map((r) =>
          r.id === refId
            ? { ...r, url: result?.url || '', features: result?.features || null, analyzing: false }
            : r
        )
      )
    } catch (err) {
      console.error('图片分析失败:', err)
      setLocalRefs((prev) =>
        prev.map((r) =>
          r.id === refId ? { ...r, analyzing: false } : r
        )
      )
    }
  }

  function handleAddTextRef() {
    const text = textDraft.trim()
    if (!text) return
    setLocalRefs((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        type: 'text',
        title: text.slice(0, 20) + (text.length > 20 ? '...' : ''),
        content: text,
        previewUrl: '',
        url: '',
        features: null,
        analyzing: false,
      },
    ])
    setTextInputOpen(false)
    setTextDraft('')
  }

  function handleRemoveLocalRef(refId) {
    setLocalRefs((prev) => {
      const target = prev.find((r) => r.id === refId)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      return prev.filter((r) => r.id !== refId)
    })
  }

  const hasSelection = selectedAssets.length > 0 || selectedProduct || localRefs.length > 0

  return (
    <>
      <div className="fixed bottom-0 left-[260px] right-0 z-20 border-t border-[var(--border-soft)] bg-[rgba(15,15,26,0.88)] px-8 py-5 backdrop-blur-xl transition-[left] duration-300 max-[1024px]:left-[72px]">
        <div className="relative mx-auto max-w-4xl">
          {panelOpen && <ParameterPanel />}

          <form
            className="rounded-2xl border border-[rgba(56,189,248,0.2)] bg-[rgba(26,26,46,0.95)] p-3 shadow-[0_8px_32px_rgba(56,189,248,0.08)]"
            onSubmit={submit}
          >
            {hasSelection ? (
              <div className="mb-3 overflow-x-auto border-b border-dashed border-[rgba(148,163,184,0.18)] pb-3">
                <div className="flex gap-2">
                  {selectedAssets.map((asset) => (
                    <SelectedAssetChip
                      key={asset.id}
                      asset={asset}
                      onRemove={handleRemoveAsset}
                    />
                  ))}
                  {selectedProduct ? (
                    <SelectedProductChip
                      product={selectedProduct}
                      onRemove={handleRemoveProduct}
                    />
                  ) : null}
                  {localRefs.map((ref) => (
                    <LocalRefChip
                      key={ref.id}
                      localRef={ref}
                      onRemove={handleRemoveLocalRef}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <textarea
              className="max-h-[200px] min-h-12 w-full resize-none bg-transparent px-2 py-1 text-sm leading-6 text-white outline-none placeholder:text-[var(--text-muted)]"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述你想生成的视频，Shift + Enter 换行"
            />

            <div className="mt-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <button
                    className={`relative rounded-xl p-2.5 transition ${
                      hasSelection
                        ? 'bg-[rgba(56,189,248,0.12)] text-white'
                        : 'text-[var(--text-muted)] hover:bg-[rgba(56,189,248,0.12)] hover:text-white'
                    }`}
                    type="button"
                    aria-label="添加素材或商品"
                    onClick={() => setMenuOpen((open) => !open)}
                  >
                    <Plus size={18} />
                    {selectedAssets.length > 0 ? (
                      <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-[#38bdf8] px-1 text-[10px] font-semibold text-[#08131f]">
                        {selectedAssets.length}
                      </span>
                    ) : null}
                    {selectedProduct ? (
                      <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-[#a78bfa] px-1 text-[10px] font-semibold text-white">
                        <Package size={10} />
                      </span>
                    ) : null}
                    {!selectedAssets.length && !selectedProduct && localRefs.length > 0 ? (
                      <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-[#22c55e] px-1 text-[10px] font-semibold text-[#07131f]">
                        {localRefs.length}
                      </span>
                    ) : null}
                  </button>
                  {menuOpen && (
                    <PlusMenu
                      onSelect={handlePlusMenuSelect}
                      onClose={() => setMenuOpen(false)}
                    />
                  )}
                </div>
                <button
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white"
                  type="button"
                  onClick={() => setPanelOpen((open) => !open)}
                >
                  <SlidersHorizontal size={18} />
                  参数
                </button>
              </div>

              <button
                className={`grid h-10 w-10 place-items-center rounded-lg ${
                  canSend
                    ? 'bg-[linear-gradient(135deg,#38BDF8_0%,#22C55E_100%)] text-[#07131f] shadow-[0_4px_24px_rgba(56,189,248,0.22)]'
                    : 'cursor-not-allowed bg-[rgba(148,163,184,0.12)] text-[rgba(148,163,184,0.5)]'
                }`}
                type="submit"
                disabled={!canSend}
                aria-label="Send message"
              >
                <Send size={18} />
              </button>
            </div>
          </form>
        </div>
      </div>

      <MaterialPickerModal
        open={pickerOpen}
        selectedAssets={selectedAssets.filter((asset) => selectedAssetIds.has(asset.id))}
        onClose={() => setPickerOpen(false)}
        onConfirm={handleConfirmAssets}
      />

      <ProductPickerModal
        open={productPickerOpen}
        selectedProduct={selectedProduct}
        onClose={() => setProductPickerOpen(false)}
        onConfirm={handleConfirmProduct}
      />

      {/* 隐藏的文件选择器 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* 文本参考输入弹窗 */}
      {textInputOpen ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[rgba(3,7,18,0.72)] px-4 backdrop-blur-sm">
          <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-[var(--border-soft)] bg-[rgba(15,15,26,0.98)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border-soft)] px-5 py-4">
              <h3 className="m-0 text-base font-semibold text-white">粘贴参考文本</h3>
              <button
                type="button"
                className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
                onClick={() => setTextInputOpen(false)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-5">
              <textarea
                className="max-h-[300px] min-h-[120px] w-full resize-none rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-[var(--text-muted)]"
                value={textDraft}
                onChange={(e) => setTextDraft(e.target.value)}
                placeholder="粘贴参考文本内容..."
                autoFocus
              />
            </div>
            <div className="flex justify-end gap-3 border-t border-[var(--border-soft)] px-5 py-4">
              <button
                type="button"
                className="rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                onClick={() => setTextInputOpen(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded-xl bg-[linear-gradient(135deg,#22c55e_0%,#16a34a_100%)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                disabled={!textDraft.trim()}
                onClick={handleAddTextRef}
              >
                添加参考
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
