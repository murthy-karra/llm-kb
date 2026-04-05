import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiFetch } from '../lib/api'

function nanoid() {
  return crypto.randomUUID()
}

const MAX_FILE_SIZE = 10 * 1024 * 1024
const UPLOAD_CONCURRENCY = 4
const POLL_INTERVAL = 5000

const ALLOWED_CONTENT_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
}

const EXTENSION_TO_MIME = {
  '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  '.md': 'text/markdown',
  '.txt': 'text/plain',
}

function resolveContentType(file) {
  if (file.type && Object.keys(ALLOWED_CONTENT_TYPES).includes(file.type)) {
    return file.type
  }
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  return EXTENSION_TO_MIME[ext] || file.type || ''
}

function isAllowedType(contentType) {
  return Object.keys(ALLOWED_CONTENT_TYPES).includes(contentType)
}

export const useUploadsStore = defineStore('uploads', () => {
  const batches = ref(new Map())
  const activeBatchId = ref(null)
  let pollingTimer = null
  let beforeUnloadHandler = null

  const activeBatch = computed(() => {
    if (!activeBatchId.value) return null
    return batches.value.get(activeBatchId.value) || null
  })

  function overallProgress(batchId) {
    const batch = batches.value.get(batchId)
    if (!batch) return null

    const files = Array.from(batch.files.values())
    const nonRejected = files.filter(f => f.status !== 'rejected')
    const total = nonRejected.length
    const queued = nonRejected.filter(f => f.status === 'queued').length
    const uploading = nonRejected.filter(f => f.status === 'uploading').length
    const pending = nonRejected.filter(f => f.status === 'pending_scan').length
    const complete = nonRejected.filter(f => f.status === 'clean').length
    const failed = nonRejected.filter(f => f.status.startsWith('failed')).length

    const bytesUploaded = nonRejected.reduce((sum, f) => sum + (f.sizeBytes * f.uploadProgress / 100), 0)
    const bytesTotal = nonRejected.reduce((sum, f) => sum + f.sizeBytes, 0)

    return { queued, uploading, pending, complete, failed, total, bytesUploaded, bytesTotal }
  }

  function filesByFolder(batchId) {
    const batch = batches.value.get(batchId)
    if (!batch) return {}

    const groups = {}
    Array.from(batch.files.values()).forEach(file => {
      if (file.status === 'rejected') return

      const parts = file.relativePath.split('/').filter(Boolean)
      const folder = parts[0] || 'Files'

      if (!groups[folder]) {
        groups[folder] = { files: [] }
      }

      groups[folder].files.push(file)
    })

    return groups
  }

  function addFiles(wikiId, fileList) {
    const batchId = nanoid()
    const files = new Map()

    fileList.forEach(file => {
      const fileId = nanoid()

      // Extract relative path: prefer custom relativePath (from drag-drop), then webkitRelativePath
      let relativePath = ''
      if (file.relativePath) {
        // From drag-and-drop: relativePath is fullPath like /folder/subfolder/file.pdf
        // Strip the filename to get the directory path
        const parts = file.relativePath.replace(/^\//, '').split('/')
        relativePath = parts.slice(0, -1).join('/')
      } else if (file.webkitRelativePath) {
        const parts = file.webkitRelativePath.split('/')
        relativePath = parts.slice(0, -1).join('/')
      }

      let status = 'validating'
      let rejectReason = null
      const contentType = resolveContentType(file)

      if (file.size > MAX_FILE_SIZE) {
        status = 'rejected'
        rejectReason = `File size exceeds ${(MAX_FILE_SIZE / (1024 * 1024)).toFixed(0)}MB limit`
      } else if (!isAllowedType(contentType)) {
        status = 'rejected'
        rejectReason = `File type "${file.name.split('.').pop()}" not allowed`
      } else if (relativePath.includes('..') || file.name.includes('..')) {
        status = 'rejected'
        rejectReason = 'Invalid path characters'
      } else {
        status = 'queued'
      }

      files.set(fileId, {
        fileId,
        file,
        filename: file.name,
        relativePath,
        sizeBytes: file.size,
        contentType,
        status,
        rejectReason,
        uploadProgress: 0,
        presignedUrl: null,
        presignedFields: null,
        s3Key: null,
        wikiFileId: null,
        xhr: null,
      })
    })

    batches.value.set(batchId, {
      id: batchId,
      wikiId,
      files,
      startedAt: new Date(),
    })

    activeBatchId.value = batchId

    return batchId
  }

  async function startUpload(batchId) {
    const batch = batches.value.get(batchId)
    if (!batch) throw new Error('Batch not found')

    const files = Array.from(batch.files.values()).filter(f => f.status === 'queued')
    if (files.length === 0) return

    try {
      const res = await apiFetch(`/api/wikis/${batch.wikiId}/uploads/presign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          files: files.map(f => ({
            filename: f.filename,
            relative_path: f.relativePath,
            size_bytes: f.sizeBytes,
            content_type: f.contentType,
          })),
        }),
      })

      if (!res.ok) {
        throw new Error(`Failed to get presigned URLs: ${res.status}`)
      }

      const data = await res.json()

      data.accepted.forEach(accepted => {
        const file = Array.from(batch.files.values()).find(
          f => f.filename === accepted.filename && f.relativePath === accepted.relative_path
        )
        if (file) {
          file.presignedUrl = accepted.presigned_url
          file.presignedFields = accepted.presigned_fields
          file.s3Key = accepted.s3_key
          file.wikiFileId = accepted.file_id
        }
      })

      data.rejected.forEach(rejected => {
        const file = Array.from(batch.files.values()).find(
          f => f.filename === rejected.filename && f.relativePath === rejected.relative_path
        )
        if (file) {
          file.status = 'rejected'
          file.rejectReason = rejected.reject_reason
        }
      })

      const queue = Array.from(batch.files.values()).filter(f => f.presignedUrl)
      runUploadQueue(batchId, queue)

    } catch (e) {
      console.error('Upload failed:', e)
      Array.from(batch.files.values()).filter(f => f.status === 'queued').forEach(f => {
        f.status = 'failed_upload'
        f.rejectReason = e.message || 'Network error - please try again'
      })
    }
  }

  function runUploadQueue(batchId, queue) {
    const batch = batches.value.get(batchId)
    if (!batch) return

    setBeforeUnloadWarning()

    let activeCount = 0
    let nextIndex = 0

    function uploadNext() {
      // Check if all done
      if (nextIndex >= queue.length && activeCount === 0) {
        clearBeforeUnloadWarning()
        const confirmedFiles = Array.from(batch.files.values()).filter(f => f.status === 'pending_scan')
        if (confirmedFiles.length > 0) {
          startPolling(batchId)
        }
        return
      }

      // Fill available slots
      while (activeCount < UPLOAD_CONCURRENCY && nextIndex < queue.length) {
        const file = queue[nextIndex]
        nextIndex++
        activeCount++

        uploadFile(batchId, file, () => {
          activeCount--
          uploadNext()
        })
      }
    }

    uploadNext()
  }

  function uploadFile(batchId, file, onComplete) {
    file.status = 'uploading'

    // Use presigned POST: build FormData with fields + file
    const formData = new FormData()
    if (file.presignedFields) {
      Object.entries(file.presignedFields).forEach(([key, value]) => {
        formData.append(key, value)
      })
    }
    formData.append('file', file.file)

    const xhr = new XMLHttpRequest()
    file.xhr = xhr

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        file.uploadProgress = Math.round((e.loaded / e.total) * 100)
      }
    }

    xhr.onload = async () => {
      file.xhr = null
      if (xhr.status >= 200 && xhr.status < 300) {
        file.uploadProgress = 100
        file.status = 'pending_scan'

        try {
          await confirmUploadFile(batchId, file)
        } catch (e) {
          file.status = 'failed_upload'
          file.rejectReason = 'Upload confirmation failed'
        }
      } else {
        file.status = 'failed_upload'
        file.rejectReason = `Upload failed with status ${xhr.status}`
      }
      onComplete()
    }

    xhr.onerror = () => {
      file.xhr = null
      file.status = 'failed_upload'
      file.rejectReason = 'Network error - please check your connection'
      onComplete()
    }

    xhr.onabort = () => {
      file.xhr = null
      file.status = 'failed_upload'
      file.rejectReason = 'Upload cancelled'
      onComplete()
    }

    xhr.open('POST', file.presignedUrl)
    xhr.send(formData)
  }

  async function confirmUploadFile(batchId, file) {
    const batch = batches.value.get(batchId)
    if (!batch || !file.wikiFileId) return

    const res = await apiFetch(`/api/wikis/${batch.wikiId}/uploads/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids: [file.wikiFileId] }),
    })

    if (!res.ok) {
      throw new Error('Failed to confirm upload')
    }
  }

  function startPolling(batchId) {
    if (pollingTimer) clearInterval(pollingTimer)

    const poll = async () => {
      const batch = batches.value.get(batchId)
      if (!batch) {
        clearInterval(pollingTimer)
        pollingTimer = null
        return
      }

      try {
        const res = await apiFetch(`/api/wikis/${batch.wikiId}/uploads/status`)

        if (!res.ok) return

        const data = await res.json()

        data.files.forEach(fileStatus => {
          const file = Array.from(batch.files.values()).find(f => f.wikiFileId === fileStatus.file_id)
          if (file) {
            file.status = fileStatus.status
          }
        })

        if (data.all_complete) {
          clearInterval(pollingTimer)
          pollingTimer = null
        }
      } catch (e) {
        console.error('Polling error:', e)
      }
    }

    pollingTimer = setInterval(poll, POLL_INTERVAL)
    poll()
  }

  function cancelFile(batchId, fileId) {
    const batch = batches.value.get(batchId)
    if (!batch) return

    const file = batch.files.get(fileId)
    if (!file) return

    if (file.status === 'uploading' && file.xhr) {
      file.xhr.abort()
    } else if (file.status === 'queued') {
      batch.files.delete(fileId)
    }

    if (batch.files.size === 0) {
      cancelBatch(batchId)
    }
  }

  async function retryFile(batchId, fileId) {
    const batch = batches.value.get(batchId)
    if (!batch) return

    const file = batch.files.get(fileId)
    if (!file) return

    file.status = 'queued'
    file.uploadProgress = 0
    file.presignedUrl = null
    file.presignedFields = null
    file.s3Key = null
    file.wikiFileId = null
    file.xhr = null

    await startUpload(batchId)
  }

  function cancelBatch(batchId) {
    const batch = batches.value.get(batchId)
    if (batch) {
      // Abort any in-progress uploads
      Array.from(batch.files.values()).forEach(f => {
        if (f.status === 'uploading' && f.xhr) {
          f.xhr.abort()
        }
      })
    }

    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }

    clearBeforeUnloadWarning()

    if (activeBatchId.value === batchId) {
      activeBatchId.value = null
    }

    batches.value.delete(batchId)
  }

  function setBeforeUnloadWarning() {
    if (beforeUnloadHandler) return

    beforeUnloadHandler = (e) => {
      e.preventDefault()
      e.returnValue = 'You have uploads in progress. Are you sure you want to leave?'
    }
    window.addEventListener('beforeunload', beforeUnloadHandler)
  }

  function clearBeforeUnloadWarning() {
    if (beforeUnloadHandler) {
      window.removeEventListener('beforeunload', beforeUnloadHandler)
      beforeUnloadHandler = null
    }
  }

  return {
    batches,
    activeBatchId,
    activeBatch,
    overallProgress,
    filesByFolder,
    addFiles,
    startUpload,
    cancelFile,
    retryFile,
    cancelBatch,
  }
})
