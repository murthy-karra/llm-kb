<script setup>
import { computed, onMounted } from 'vue'
import { useKbStore } from '../stores/kb'

const store = useKbStore()

onMounted(() => {
  store.fetchArticles()
})

const grouped = computed(() => {
  const groups = {}
  for (const a of store.articles) {
    const cat = a.category || 'uncategorized'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(a)
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
})
</script>

<template>
  <div>
    <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Wiki</h1>
    <p class="text-[13px] text-text-muted mt-1 mb-6">Browse articles by category</p>

    <div v-for="[category, articles] in grouped" :key="category" class="mb-6">
      <h2 class="text-[11px] font-semibold text-accent uppercase tracking-wider mb-2 px-1">
        {{ category.replace(/-/g, ' ') }}
      </h2>
      <div class="card overflow-hidden">
        <RouterLink
          v-for="(article, i) in articles"
          :key="article.path"
          :to="`/wiki/${article.path}`"
          class="list-row block px-5 py-3.5"
          :class="i < articles.length - 1 ? 'border-b border-border' : ''"
        >
          <div class="text-[13px] font-medium text-text-heading">{{ article.title }}</div>
          <div class="text-[12px] text-text-muted mt-0.5 line-clamp-1">{{ article.preview }}</div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
