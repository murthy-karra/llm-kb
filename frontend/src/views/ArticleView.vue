<script setup>
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Marked } from 'marked'
import hljs from 'highlight.js'
import { BookOpen, Tag, FileText, Clock, Link, ImagePlus, Loader2 } from 'lucide-vue-next'
import { useKbStore } from '../stores/kb'

const route = useRoute()
const router = useRouter()
const store = useKbStore()

const article = ref(null)
const renderedContent = ref('')
const contentEl = ref(null)
const toc = ref([])
const heroImage = ref(null)
const imageLoading = ref(false)
const imageError = ref(false)

const marked = new Marked({
  renderer: {
    code({ text, lang }) {
      if (lang && hljs.getLanguage(lang)) {
        const highlighted = hljs.highlight(text, { language: lang }).value
        return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`
      }
      return `<pre><code>${text}</code></pre>`
    },
  },
})

function renderWikilinks(content) {
  return content.replace(/\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]/g, (_, path, label) => {
    const display = label || path.replace(/-/g, ' ')
    return `<a class="wikilink" data-wiki="${path}">${display}</a>`
  })
}

function extractToc(content) {
  const headings = []
  const regex = /^(#{2,3})\s+(.+)$/gm
  let match
  while ((match = regex.exec(content)) !== null) {
    const level = match[1].length
    const text = match[2].replace(/\*\*/g, '').trim()
    if (text.toLowerCase() === 'sources') continue
    const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
    headings.push({ level, text, id })
  }
  return headings
}

// Related articles: match tags to other articles
const relatedArticles = computed(() => {
  if (!article.value || !store.articles.length) return []
  const tags = article.value.metadata.tags || []
  const currentPath = route.params.path
  return store.articles
    .filter((a) => {
      if (a.path === currentPath) return false
      const slug = a.path.replace(/\.md$/, '').split('/').pop()
      return tags.includes(slug)
    })
    .slice(0, 8)
})

// Key facts extracted from content (word count, heading count, etc.)
const keyFacts = computed(() => {
  if (!article.value) return []
  const content = article.value.content
  const facts = []
  const words = content.split(/\s+/).length
  facts.push({ label: 'Word count', value: words.toLocaleString() })
  const headings = (content.match(/^#{2,3}\s/gm) || []).length
  facts.push({ label: 'Sections', value: headings })
  const links = (content.match(/\[\[/g) || []).length
  facts.push({ label: 'Wiki links', value: links })
  const sources = article.value.metadata.sources || []
  facts.push({ label: 'Source docs', value: sources.length })
  return facts
})

function articleSlug() {
  return route.params.path?.replace(/\.md$/, '').split('/').pop() || ''
}

async function checkImage() {
  const slug = articleSlug()
  heroImage.value = null
  imageError.value = false
  try {
    const res = await fetch(`/api/image/${slug}`, { method: 'HEAD' })
    if (res.ok) {
      heroImage.value = `/api/image/${slug}?t=${Date.now()}`
    }
  } catch {}
}

async function generateImage() {
  const slug = articleSlug()
  const meta = article.value.metadata
  imageLoading.value = true
  imageError.value = false
  try {
    await store.generateImage(
      slug,
      meta.title,
      meta.category,
      article.value.content.slice(0, 300),
    )
    heroImage.value = `/api/image/${slug}?t=${Date.now()}`
  } catch {
    imageError.value = true
  } finally {
    imageLoading.value = false
  }
}

async function loadArticle() {
  const path = route.params.path
  if (!path) return
  article.value = await store.fetchArticle(path)

  toc.value = extractToc(article.value.content)
  checkImage()

  const withLinks = renderWikilinks(article.value.content)
  renderedContent.value = await marked.parse(withLinks)

  await nextTick()
  if (contentEl.value) {
    // Add IDs to headings for TOC navigation
    contentEl.value.querySelectorAll('h2, h3').forEach((el) => {
      const id = el.textContent.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
      el.id = id
    })

    contentEl.value.querySelectorAll('.wikilink').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.preventDefault()
        const wiki = el.dataset.wiki
        const match = store.articles.find(
          (a) => a.path.includes(wiki) || a.path.endsWith(`${wiki}.md`)
        )
        if (match) {
          router.push(`/wiki/${match.path}`)
        }
      })
    })
  }
}

function scrollToHeading(id) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(async () => {
  if (!store.articles.length) await store.fetchArticles()
  loadArticle()
})

watch(() => route.params.path, loadArticle)
</script>

<template>
  <div v-if="article">
    <div class="mb-5">
      <RouterLink to="/wiki" class="text-[13px] font-medium text-accent hover:text-accent-hover transition-colors duration-150">&larr; Back to Wiki</RouterLink>
    </div>

    <div class="flex gap-6 items-start">
      <!-- Main content -->
      <div class="flex-1 min-w-0">
        <div class="card p-8">
          <!-- Header -->
          <div class="mb-6 pb-5 border-b border-border">
            <h1 class="text-[22px] font-semibold text-text-heading tracking-tight leading-tight">{{ article.metadata.title }}</h1>
            <div class="flex flex-wrap gap-1.5 mt-3">
              <span class="text-[11px] font-semibold bg-accent-subtle text-accent rounded-md px-2.5 py-1">{{ article.metadata.category }}</span>
              <span
                v-for="tag in article.metadata.tags"
                :key="tag"
                class="text-[11px] font-medium bg-surface text-text-muted rounded-md px-2.5 py-1"
              >{{ tag }}</span>
            </div>
          </div>

          <!-- Content -->
          <div
            ref="contentEl"
            class="prose max-w-none"
            v-html="renderedContent"
          />

          <!-- Footer -->
          <div class="mt-8 pt-5 border-t border-border text-[12px] text-text-muted space-y-1">
            <div v-if="article.metadata.sources">
              <span class="font-medium text-text-body">Sources:</span> {{ article.metadata.sources.join(', ') }}
            </div>
            <div v-if="article.metadata.updated">
              <span class="font-medium text-text-body">Updated:</span> {{ new Date(article.metadata.updated).toLocaleDateString() }}
            </div>
          </div>
        </div>
      </div>

      <!-- Right sidebar -->
      <div class="w-64 shrink-0 space-y-4 sticky top-8">
        <!-- Hero Image -->
        <div class="card overflow-hidden" v-if="heroImage">
          <img :src="heroImage" :alt="article.metadata.title" class="w-full h-40 object-cover" />
        </div>
        <div v-else class="card overflow-hidden">
          <div class="h-36 bg-gradient-to-br from-surface to-border flex items-center justify-center">
            <button
              v-if="!imageLoading"
              @click="generateImage"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-card-bg rounded-lg text-[11px] font-medium text-text-body shadow-btn hover:shadow-btn-hover hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer"
            >
              <ImagePlus :size="13" :stroke-width="2" />
              Generate image
            </button>
            <div v-else class="flex items-center gap-1.5 text-[11px] text-text-muted">
              <Loader2 :size="13" :stroke-width="2" class="animate-spin" />
              Generating...
            </div>
          </div>
          <div v-if="imageError" class="px-3 py-2 text-[11px] text-red-500 bg-red-50">
            Failed to generate. Check OpenAI API key.
          </div>
        </div>

        <!-- Key Facts infobox -->
        <div class="card p-4">
          <h3 class="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <BookOpen :size="12" :stroke-width="2.5" />
            Quick Facts
          </h3>
          <div class="space-y-2">
            <div v-for="fact in keyFacts" :key="fact.label" class="flex justify-between items-center">
              <span class="text-[12px] text-text-body">{{ fact.label }}</span>
              <span class="text-[12px] font-semibold text-text-heading">{{ fact.value }}</span>
            </div>
          </div>
          <div class="mt-3 pt-3 border-t border-border">
            <div class="flex items-center gap-1.5 text-[12px] text-text-muted">
              <Clock :size="11" :stroke-width="2" />
              {{ new Date(article.metadata.updated).toLocaleDateString() }}
            </div>
          </div>
        </div>

        <!-- Table of Contents -->
        <div class="card p-4" v-if="toc.length > 0">
          <h3 class="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <FileText :size="12" :stroke-width="2.5" />
            Contents
          </h3>
          <nav class="space-y-0.5">
            <button
              v-for="heading in toc"
              :key="heading.id"
              @click="scrollToHeading(heading.id)"
              class="block w-full text-left text-[12px] py-1 rounded transition-colors duration-150 cursor-pointer hover:text-accent"
              :class="heading.level === 3 ? 'pl-3 text-text-muted' : 'text-text-body font-medium'"
            >
              {{ heading.text }}
            </button>
          </nav>
        </div>

        <!-- Related Articles -->
        <div class="card p-4" v-if="relatedArticles.length > 0">
          <h3 class="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Link :size="12" :stroke-width="2.5" />
            Related
          </h3>
          <div class="space-y-1">
            <RouterLink
              v-for="related in relatedArticles"
              :key="related.path"
              :to="`/wiki/${related.path}`"
              class="block text-[12px] font-medium text-text-body hover:text-accent py-1 transition-colors duration-150"
            >
              {{ related.title }}
            </RouterLink>
          </div>
        </div>

        <!-- Source Documents -->
        <div class="card p-4" v-if="article.metadata.sources?.length">
          <h3 class="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Tag :size="12" :stroke-width="2.5" />
            Sources
          </h3>
          <div class="space-y-1">
            <div
              v-for="source in article.metadata.sources"
              :key="source"
              class="text-[11px] text-text-muted truncate"
            >
              {{ source }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
