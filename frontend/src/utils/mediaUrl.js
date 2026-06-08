export function appendVideoCacheBuster(url, ...tokens) {
  if (!url) return url

  const stableToken = tokens.find((token) => token !== undefined && token !== null && token !== '')
  if (!stableToken) return url

  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}v=${encodeURIComponent(String(stableToken))}`
}
