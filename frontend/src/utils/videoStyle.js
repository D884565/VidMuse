/** 视频风格标识 → 中文标签映射 */
const VIDEO_STYLE_LABELS = {
  cinematic: '电影感',
  product: '产品展示',
  anime: '动漫风',
  realistic: '写实风',
  lifestyle: '生活方式',
  fashion: '时尚风',
  tech: '科技风',
  food: '美食风',
}

export function formatVideoStyle(style) {
  if (style == null) return ''

  const normalizedStyle = String(style).trim()
  if (!normalizedStyle) return ''

  return VIDEO_STYLE_LABELS[normalizedStyle.toLowerCase()] || normalizedStyle
}

export { VIDEO_STYLE_LABELS }
