import { Package, Plus, Send, SlidersHorizontal, X, Image as ImageIcon } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import MaterialPickerModal from './MaterialPickerModal.jsx'
import ProductPickerModal from './ProductPickerModal.jsx'
import ParameterPanel from '../Parameters/ParameterPanel.jsx'
import { formatSelectedAssetLabel, getAssetTypeLabel } from './materialPrompt.js'

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
      className="absolute bottom-full left-0 mb-2 w-44 overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(22,22,40,0.98)] py-1 shadow-2xl backdrop-blur-xl"
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
  const [menuOpen, setMenuOpen] = useState(false)

  const canSend = value.trim().length > 0
  const selectedAssetIds = useMemo(
    () => new Set(selectedAssets.map((asset) => asset.id)),
    [selectedAssets]
  )

  function submit(event) {
    event.preventDefault()
    if (!canSend) return
    onSend({
      content: value,
      selectedAssets,
      selectedProduct,
    })
    setValue('')
    setSelectedAssets([])
    setSelectedProduct(null)
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
    }
  }

  const hasSelection = selectedAssets.length > 0 || selectedProduct

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
    </>
  )
}
