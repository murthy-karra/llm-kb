<script setup>
import { onMounted, ref } from 'vue'
import { useKbStore } from '../stores/kb'

const store = useKbStore()
const url = ref('')
const ingestResult = ref(null)

onMounted(() => {
  store.fetchRawFiles()
})

async function handleIngest() {
  if (!url.value.trim()) return
  ingestResult.value = null
  ingestResult.value = await store.ingestURL(url.value.trim())
  url.value = ''
  store.fetchRawFiles()
}
</script>

<template>
  <div>
    <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Raw Sources</h1>
    <p class="text-[13px] text-text-muted mt-1 mb-6">Ingested documents before compilation</p>

    <!-- Ingest URL -->
    <div class="flex gap-2 mb-5">
      <input
        v-model="url"
        type="text"
        placeholder="https://example.com/article"
        class="input flex-1"
        @keyup.enter="handleIngest"
      />
      <button @click="handleIngest" :disabled="store.loading || !url.trim()" class="btn-primary">
        {{ store.loading ? 'Ingesting...' : 'Ingest URL' }}
      </button>
    </div>

    <div v-if="ingestResult" class="card p-4 mb-5">
      <p class="text-[13px] text-text-body">
        Ingested: <span class="font-semibold text-accent">{{ ingestResult.path }}</span>
      </p>
    </div>

    <!-- File list -->
    <div class="card overflow-hidden">
      <div
        v-for="(file, i) in store.rawFiles"
        :key="file.path"
        class="list-row px-5 py-3.5 flex justify-between items-center"
        :class="i < store.rawFiles.length - 1 ? 'border-b border-border' : ''"
      >
        <span class="text-[13px] font-medium text-text-heading">{{ file.path }}</span>
        <span class="text-[12px] text-text-muted">{{ file.size_kb }} KB</span>
      </div>
      <div v-if="!store.rawFiles.length" class="px-5 py-10 text-center text-[13px] text-text-muted">
        No raw sources yet. Ingest a URL above.
      </div>
    </div>
  </div>
</template>
