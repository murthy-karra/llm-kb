<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Marked } from 'marked'
import hljs from 'highlight.js'
import { useKbStore } from '../stores/kb'

const route = useRoute()
const router = useRouter()
const store = useKbStore()

const article = ref(null)
const renderedContent = ref('')
const contentEl = ref(null)

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

async function loadArticle() {
  const path = route.params.path
  if (!path) return
  article.value = await store.fetchArticle(path)
  const withLinks = renderWikilinks(article.value.content)
  renderedContent.value = await marked.parse(withLinks)

  await nextTick()
  if (contentEl.value) {
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
</template>
