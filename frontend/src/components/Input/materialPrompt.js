const ASSET_TYPE_LABELS = {
  image: '图片',
  video: '视频',
  audio: '音频',
  text: '文本',
}

export function getAssetTypeLabel(type) {
  return ASSET_TYPE_LABELS[type] || '素材'
}

export function formatSelectedAssetLabel(asset) {
  const title = (asset?.title || asset?.name || '').trim()
  if (title) return title
  return `未命名${getAssetTypeLabel(asset?.type)}`
}

export function normalizeSelectedAsset(asset) {
  return {
    id: asset.id,
    type: asset.type,
    typeLabel: getAssetTypeLabel(asset.type),
    title: formatSelectedAssetLabel(asset),
    url: asset.url || '',
  }
}

export function buildReferenceMaterialsPrompt(selectedAssets = []) {
  const normalizedAssets = selectedAssets
    .filter((asset) => asset?.id != null)
    .map(normalizeSelectedAsset)

  if (!normalizedAssets.length) {
    return ''
  }

  const materialLines = normalizedAssets.map(
    (asset, index) => `${index + 1}. [${asset.typeLabel}] ${asset.title}（asset_id: ${asset.id}）`
  )

  return [
    '参考素材：',
    ...materialLines,
    '',
    '要求：',
    '- 优先参考以上素材的主体、配色、构图、镜头或氛围',
    '- 若素材之间冲突，以用户文字要求为主',
  ].join('\n')
}

export function buildProductPrompt(product) {
  if (!product) return ''
  const lines = ['商品信息：']
  if (product.name) lines.push(`- 名称：${product.name}`)
  if (product.brand) lines.push(`- 品牌：${product.brand}`)
  if (product.price) lines.push(`- 价格：${product.price}`)
  if (product.description) lines.push(`- 描述：${product.description}`)
  if (product.main_image_url) lines.push(`- 主图：${product.main_image_url}`)
  if (product.id) lines.push(`- product_id: ${product.id}`)
  return lines.join('\n')
}

export function buildChatSubmission({ content, selectedAssets = [], selectedProduct = null }) {
  const displayContent = (content || '').trim()
  const normalizedAssets = selectedAssets
    .filter((asset) => asset?.id != null)
    .map(normalizeSelectedAsset)
  const materialPrompt = buildReferenceMaterialsPrompt(normalizedAssets)
  const productPrompt = buildProductPrompt(selectedProduct)

  const parts = [displayContent]
  if (materialPrompt) parts.push(materialPrompt)
  if (productPrompt) parts.push(productPrompt)

  return {
    displayContent,
    content: parts.join('\n\n'),
    selectedAssets: normalizedAssets,
    selectedProduct: selectedProduct || null,
  }
}
