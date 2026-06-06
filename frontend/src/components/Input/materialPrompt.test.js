import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildChatSubmission,
  buildProductPrompt,
  buildReferenceMaterialsPrompt,
  formatSelectedAssetLabel,
} from './materialPrompt.js'

test('buildReferenceMaterialsPrompt renders selected materials into numbered prompt lines', () => {
  const prompt = buildReferenceMaterialsPrompt([
    { id: 101, type: 'image', title: '防晒喷雾主图' },
    { id: 205, type: 'video', title: '达人实拍片段' },
    { id: 308, type: 'audio', title: '海风环境音' },
  ])

  assert.match(prompt, /参考素材：/)
  assert.match(prompt, /1\. \[图片\] 防晒喷雾主图（asset_id: 101）/)
  assert.match(prompt, /2\. \[视频\] 达人实拍片段（asset_id: 205）/)
  assert.match(prompt, /3\. \[音频\] 海风环境音（asset_id: 308）/)
  assert.match(prompt, /优先参考以上素材的主体、配色、构图、镜头或氛围/)
})

test('buildChatSubmission keeps display content clean while augmenting the submitted content', () => {
  const result = buildChatSubmission({
    content: '做一条夏日防晒喷雾带货视频，画面清爽一点',
    selectedAssets: [
      { id: 101, type: 'image', title: '防晒喷雾主图', url: 'https://example.com/a.png' },
      { id: 205, type: 'video', title: '达人实拍片段', url: 'https://example.com/b.mp4' },
    ],
  })

  assert.equal(result.displayContent, '做一条夏日防晒喷雾带货视频，画面清爽一点')
  assert.match(result.content, /做一条夏日防晒喷雾带货视频，画面清爽一点/)
  assert.match(result.content, /参考素材：/)
  assert.equal(result.selectedAssets.length, 2)
  assert.deepEqual(result.selectedAssets[0], {
    id: 101,
    type: 'image',
    typeLabel: '图片',
    title: '防晒喷雾主图',
    url: 'https://example.com/a.png',
  })
})

test('formatSelectedAssetLabel falls back safely when title is missing', () => {
  assert.equal(formatSelectedAssetLabel({ type: 'image', title: '' }), '未命名图片')
  assert.equal(formatSelectedAssetLabel({ type: 'video' }), '未命名视频')
  assert.equal(formatSelectedAssetLabel({ type: 'audio', title: '海风环境音' }), '海风环境音')
})

test('buildProductPrompt renders product info into structured prompt', () => {
  const prompt = buildProductPrompt({
    id: 42,
    name: '防晒喷雾',
    brand: 'SunCare',
    price: 99.9,
    description: '清爽不油腻',
  })

  assert.match(prompt, /商品信息：/)
  assert.match(prompt, /名称：防晒喷雾/)
  assert.match(prompt, /品牌：SunCare/)
  assert.match(prompt, /价格：99\.9/)
  assert.match(prompt, /描述：清爽不油腻/)
  assert.match(prompt, /product_id: 42/)
})

test('buildProductPrompt returns empty string for null product', () => {
  assert.equal(buildProductPrompt(null), '')
  assert.equal(buildProductPrompt(undefined), '')
})

test('buildChatSubmission includes product prompt when product is selected', () => {
  const result = buildChatSubmission({
    content: '做一个带货视频',
    selectedAssets: [],
    selectedProduct: { id: 42, name: '防晒喷雾', brand: 'SunCare', price: 99.9 },
  })

  assert.equal(result.displayContent, '做一个带货视频')
  assert.match(result.content, /商品信息：/)
  assert.match(result.content, /名称：防晒喷雾/)
  assert.equal(result.selectedProduct.id, 42)
})

test('buildChatSubmission works without selectedProduct parameter', () => {
  const result = buildChatSubmission({
    content: '做一个带货视频',
    selectedAssets: [],
  })

  assert.equal(result.displayContent, '做一个带货视频')
  assert.equal(result.selectedProduct, null)
  assert.doesNotMatch(result.content, /商品信息/)
})
