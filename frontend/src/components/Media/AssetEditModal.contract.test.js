import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./AssetEditModal.jsx', import.meta.url), { encoding: 'utf8' })

test('AssetEditModal resets pending action state when a different asset opens', () => {
  const effectStart = source.indexOf('useEffect(() => {')
  const effectEnd = source.indexOf('}, [asset])', effectStart)
  const effectBody = source.slice(effectStart, effectEnd)

  assert.match(effectBody, /setSaving\(false\)/)
  assert.match(effectBody, /setUploading\(false\)/)
  assert.match(effectBody, /setShowDeleteConfirm\(false\)/)
})

test('AssetEditModal clears deleting state after successful delete callback', () => {
  const deleteStart = source.indexOf('async function handleDelete()')
  const deleteEnd = source.indexOf('return (', deleteStart)
  const deleteBody = source.slice(deleteStart, deleteEnd)

  assert.match(deleteBody, /onDeleted\?\.\(asset\.id\)/)
  assert.match(deleteBody, /finally\s*{[\s\S]*setSaving\(false\)/)
})
