import { readFileSync } from 'node:fs'


test('asset service exposes text and resumable upload helpers', () => {
  const source = readFileSync('frontend/src/services/asset.js', 'utf8')

  expect(source).toContain('createTextAsset')
  expect(source).toContain('updateTextAsset')
  expect(source).toContain('initResumableUpload')
  expect(source).toContain('uploadImageChunk')
  expect(source).toContain('getUploadStatus')
  expect(source).toContain('completeResumableUpload')
  expect(source).toContain('initImageReupload')
  expect(source).toContain('completeImageReupload')
})
