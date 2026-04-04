import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useKbStore = defineStore('kb', () => {
  const status = ref(null)
  const articles = ref([])
  const rawFiles = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchStatus() {
    const res = await fetch('/api/status')
    status.value = await res.json()
  }

  async function fetchArticles() {
    const res = await fetch('/api/wiki/articles')
    const data = await res.json()
    articles.value = data.articles
  }

  async function fetchArticle(path) {
    const res = await fetch(`/api/wiki/article/${path}`)
    return await res.json()
  }

  async function fetchRawFiles() {
    const res = await fetch('/api/raw/files')
    const data = await res.json()
    rawFiles.value = data.files
  }

  const models = ref([])

  async function fetchModels() {
    const res = await fetch('/api/models')
    const data = await res.json()
    models.value = data.presets
    return data
  }

  async function askQuestion(question, model = null) {
    loading.value = true
    error.value = null
    try {
      const body = { question }
      if (model) body.model = model
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      return await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function compileWiki(full = false) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full }),
      })
      return await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function lintWiki() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/lint', { method: 'POST' })
      return await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function ingestURL(url) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/ingest/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      return await res.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function generateImage(slug, title, category, preview, style = 'hero') {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 120000)
    try {
      const res = await fetch('/api/image/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, title, category, preview, style }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(await res.text())
      return await res.json()
    } finally {
      clearTimeout(timeout)
    }
  }

  async function searchWiki(query, limit = 10) {
    const res = await fetch('http://localhost:8880/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit }),
    })
    return await res.json()
  }

  return {
    status, articles, rawFiles, models, loading, error,
    fetchStatus, fetchArticles, fetchArticle, fetchRawFiles, fetchModels,
    askQuestion, compileWiki, lintWiki, ingestURL, generateImage, searchWiki,
  }
})
