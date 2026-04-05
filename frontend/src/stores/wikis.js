import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiFetch } from '../lib/api'

export const useWikisStore = defineStore('wikis', () => {
  const wikis = ref([])
  const currentWiki = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchWikis() {
    loading.value = true
    error.value = null
    try {
      const res = await apiFetch('/api/wikis')
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || `Failed to fetch wikis (${res.status})`)
      }
      wikis.value = await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchWiki(wikiId) {
    loading.value = true
    error.value = null
    try {
      const res = await apiFetch(`/api/wikis/${wikiId}`)
      if (!res.ok) throw new Error('Failed to fetch wiki')
      currentWiki.value = await res.json()
      return currentWiki.value
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createWiki(name, description = '') {
    loading.value = true
    error.value = null
    try {
      const res = await apiFetch('/api/wikis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail || `Failed to create wiki (${res.status})`)
      }
      const data = await res.json()
      wikis.value.push(data)
      return data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateWiki(wikiId, updates = {}) {
    loading.value = true
    error.value = null
    try {
      const res = await apiFetch(`/api/wikis/${wikiId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      if (!res.ok) throw new Error('Failed to update wiki')
      const data = await res.json()
      const idx = wikis.value.findIndex(w => w.id === wikiId)
      if (idx !== -1) wikis.value[idx] = data
      if (currentWiki.value?.id === wikiId) currentWiki.value = data
      return data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteWiki(wikiId) {
    loading.value = true
    error.value = null
    try {
      const res = await apiFetch(`/api/wikis/${wikiId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete wiki')
      wikis.value = wikis.value.filter(w => w.id !== wikiId)
      if (currentWiki.value?.id === wikiId) currentWiki.value = null
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchWikiFiles(wikiId, includePending = false) {
    const url = `/api/wikis/${wikiId}/files${includePending ? '?include_pending=true' : ''}`
    const res = await apiFetch(url)
    if (!res.ok) throw new Error('Failed to fetch wiki files')
    return await res.json()
  }

  async function fetchArticles(wikiId) {
    const res = await apiFetch(`/api/wikis/${wikiId}/articles`)
    if (!res.ok) throw new Error('Failed to fetch articles')
    return await res.json()
  }

  async function fetchArticle(wikiId, slug) {
    const res = await apiFetch(`/api/wikis/${wikiId}/articles/${slug}`)
    if (!res.ok) throw new Error('Article not found')
    return await res.json()
  }

  async function askWiki(wikiId, question) {
    const res = await apiFetch(`/api/wikis/${wikiId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => null)
      throw new Error(err?.detail || `Ask failed (${res.status})`)
    }
    return await res.json()
  }

  async function compileWiki(wikiId, full = false) {
    const res = await apiFetch(`/api/wikis/${wikiId}/compile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => null)
      throw new Error(err?.detail || `Compile failed (${res.status})`)
    }
    return await res.json()
  }

  async function lintWiki(wikiId) {
    const res = await apiFetch(`/api/wikis/${wikiId}/lint`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => null)
      throw new Error(err?.detail || `Lint failed (${res.status})`)
    }
    return await res.json()
  }

  async function getJobStatus(wikiId, jobId) {
    const res = await apiFetch(`/api/wikis/${wikiId}/jobs/${jobId}`)
    if (!res.ok) throw new Error('Failed to get job status')
    return await res.json()
  }

  async function listJobs(wikiId) {
    const res = await apiFetch(`/api/wikis/${wikiId}/jobs`)
    if (!res.ok) throw new Error('Failed to list jobs')
    return await res.json()
  }

  function pollJob(wikiId, jobId, onUpdate, intervalMs = 3000) {
    let timer = null
    const poll = async () => {
      try {
        const job = await getJobStatus(wikiId, jobId)
        onUpdate(job)
        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(timer)
        }
      } catch (e) {
        clearInterval(timer)
        onUpdate({ status: 'failed', error: e.message })
      }
    }
    timer = setInterval(poll, intervalMs)
    poll()
    return () => clearInterval(timer)
  }

  return {
    wikis,
    currentWiki,
    loading,
    error,
    fetchWikis,
    fetchWiki,
    createWiki,
    updateWiki,
    deleteWiki,
    fetchWikiFiles,
    fetchArticles,
    fetchArticle,
    askWiki,
    compileWiki,
    lintWiki,
    getJobStatus,
    listJobs,
    pollJob,
  }
})
