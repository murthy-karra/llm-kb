<script setup>
import { ref } from 'vue'
import { useKbStore } from '../stores/kb'

const store = useKbStore()
const query = ref('')
const results = ref([])
const searched = ref(false)

async function handleSearch() {
  if (!query.value.trim()) return
  searched.value = true
  const data = await store.searchWiki(query.value.trim())
  results.value = data.results
}
</script>

<template>
  <div>
    <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Search</h1>
    <p class="text-[13px] text-text-muted mt-1 mb-6">Full-text search across wiki articles</p>

    <div class="flex gap-2 mb-6">
      <input
        v-model="query"
        type="text"
        placeholder="Search wiki articles..."
        class="input flex-1"
        @keyup.enter="handleSearch"
      />
      <button @click="handleSearch" :disabled="!query.trim()" class="btn-primary !px-5">
        Search
      </button>
    </div>

    <div v-if="results.length" class="card overflow-hidden">
      <RouterLink
        v-for="(result, i) in results"
        :key="result.path"
        :to="`/wiki/${result.path}`"
        class="list-row block px-5 py-3.5"
        :class="i < results.length - 1 ? 'border-b border-border' : ''"
      >
        <div class="flex justify-between items-start">
          <div class="min-w-0 flex-1">
            <div class="text-[13px] font-medium text-text-heading">{{ result.title }}</div>
            <div class="text-[12px] text-text-muted mt-0.5 line-clamp-1">{{ result.snippet }}</div>
          </div>
          <div class="flex items-center gap-2 ml-4 shrink-0">
            <span class="text-[11px] font-medium bg-surface text-text-body rounded-md px-2 py-0.5">{{ result.category }}</span>
            <span class="text-[11px] font-medium text-text-muted tabular-nums">{{ result.score.toFixed(1) }}</span>
          </div>
        </div>
      </RouterLink>
    </div>

    <div v-else-if="searched" class="card p-8 text-center">
      <p class="text-[13px] text-text-muted">No results found.</p>
    </div>
  </div>
</template>
