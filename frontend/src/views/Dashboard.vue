<script setup>
import { onMounted, ref } from 'vue'
import { useKbStore } from '../stores/kb'

const store = useKbStore()
const compileResult = ref(null)
const lintResult = ref(null)

onMounted(() => {
  store.fetchStatus()
  store.fetchArticles()
})

async function handleCompile(full) {
  compileResult.value = null
  compileResult.value = await store.compileWiki(full)
  store.fetchStatus()
  store.fetchArticles()
}

async function handleLint() {
  lintResult.value = null
  lintResult.value = await store.lintWiki()
}
</script>

<template>
  <div>
    <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Dashboard</h1>
    <p class="text-[13px] text-text-muted mt-1 mb-6">Overview of your knowledge base</p>

    <!-- Stats cards -->
    <div class="grid grid-cols-3 gap-3 mb-8" v-if="store.status">
      <div class="stat-card p-5">
        <div class="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Raw Sources</div>
        <div class="text-[28px] font-semibold text-text-heading mt-2 leading-none">{{ store.status.raw_count }}</div>
        <div class="text-[12px] text-text-muted mt-1.5">{{ store.status.raw_size_kb }} KB total</div>
      </div>
      <div class="stat-card p-5">
        <div class="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Wiki Articles</div>
        <div class="text-[28px] font-semibold text-accent mt-2 leading-none">{{ store.status.wiki_count }}</div>
        <div class="text-[12px] text-text-muted mt-1.5">{{ store.status.wiki_size_kb }} KB total</div>
      </div>
      <div class="stat-card p-5">
        <div class="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Outputs</div>
        <div class="text-[28px] font-semibold text-text-heading mt-2 leading-none">{{ store.status.output_count }}</div>
        <div class="text-[12px] text-text-muted mt-1.5">Q&A + lint reports</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2 mb-8">
      <button @click="handleCompile(false)" :disabled="store.loading" class="btn-primary">
        {{ store.loading ? 'Working...' : 'Compile' }}
      </button>
      <button @click="handleCompile(true)" :disabled="store.loading" class="btn-primary">
        Full Rebuild
      </button>
      <button @click="handleLint" :disabled="store.loading" class="btn-secondary">
        Lint
      </button>
    </div>

    <!-- Compile result -->
    <div v-if="compileResult" class="card p-4 mb-5">
      <p class="text-[13px] text-text-body">
        Compiled <span class="font-semibold text-accent">{{ compileResult.articles_written }}</span> articles.
      </p>
    </div>

    <!-- Lint result -->
    <div v-if="lintResult" class="card p-5 mb-5">
      <h3 class="text-[13px] font-semibold text-text-heading mb-3">Lint Report</h3>
      <pre class="text-[12px] text-text-body whitespace-pre-wrap leading-relaxed bg-surface rounded-lg p-4">{{ lintResult.report }}</pre>
    </div>

    <!-- Article list -->
    <div>
      <h2 class="text-[14px] font-semibold text-text-heading mb-3">All Articles</h2>
      <div class="card overflow-hidden">
        <RouterLink
          v-for="(article, i) in store.articles"
          :key="article.path"
          :to="`/wiki/${article.path}`"
          class="list-row flex items-start gap-3 px-5 py-3.5"
          :class="i < store.articles.length - 1 ? 'border-b border-border' : ''"
        >
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-medium text-text-heading">{{ article.title }}</div>
            <div class="text-[12px] text-text-muted mt-0.5 truncate">{{ article.preview?.slice(0, 100) }}</div>
          </div>
          <span class="text-[11px] font-medium bg-surface text-text-body rounded-md px-2 py-0.5 shrink-0 mt-0.5">{{ article.category }}</span>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
