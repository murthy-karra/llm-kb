import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWikisStore = defineStore('wikis', () => {
  const wikis = ref([])
  const currentWiki = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchWikis() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/wikis', {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      })
      if (!res.ok) throw new Error('Failed to fetch wikis')
      const data = await res.json()
      wikis.value = data
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
      const res = await fetch(`/api/wikis/${wikiId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      })
      if (!res.ok) throw new Error('Failed to fetch wiki')
      const data = await res.json()
      currentWiki.value = data
      return data
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
      const res = await fetch('/api/wikis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ name, description }),
      })
      if (!res.ok) throw new Error('Failed to create wiki')
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

  async function updateWiki(wikiId, name, description = '') {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/wikis/${wikiId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ name, description }),
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
      const res = await fetch(`/api/wikis/${wikiId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      })
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
    loading.value = true
    error.value = null
    try {
      const url = `/api/wikis/${wikiId}/files${includePending ? '?include_pending=true' : ''}`
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      })
      if (!res.ok) throw new Error('Failed to fetch wiki files')
      return await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
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
  }
})