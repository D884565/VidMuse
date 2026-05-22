import { useState } from 'react'

export function useFileUpload() {
  const [files, setFiles] = useState([])

  function addFiles(fileList) {
    const nextFiles = Array.from(fileList || []).map((file) => ({
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      type: file.type || 'unknown',
    }))

    setFiles((current) => [...current, ...nextFiles])
  }

  function removeFile(id) {
    setFiles((current) => current.filter((file) => file.id !== id))
  }

  function clearFiles() {
    setFiles([])
  }

  return { files, addFiles, removeFile, clearFiles }
}
