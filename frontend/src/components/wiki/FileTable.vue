<script setup>
import { ref, computed } from 'vue'
import { FileText, ChevronUp, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  files: { type: Array, required: true },
  pageSize: { type: Number, default: 25 },
})

const filter = ref('')
const sortField = ref('filename')
const sortAsc = ref(true)
const visibleCount = ref(props.pageSize)

const filtered = computed(() => {
  const q = filter.value.toLowerCase().trim()
  if (!q) return props.files
  return props.files.filter(f =>
    f.filename.toLowerCase().includes(q) ||
    (f.relative_path && f.relative_path.toLowerCase().includes(q))
  )
})

const sorted = computed(() => {
  const field = sortField.value
  const dir = sortAsc.value ? 1 : -1
  return [...filtered.value].sort((a, b) => {
    let av, bv
    if (field === 'filename') {
      av = a.filename.toLowerCase()
      bv = b.filename.toLowerCase()
    } else if (field === 'size_bytes') {
      av = a.size_bytes
      bv = b.size_bytes
    } else if (field === 'transferred_at') {
      av = a.transferred_at || a.created_at || ''
      bv = b.transferred_at || b.created_at || ''
    }
    if (av < bv) return -dir
    if (av > bv) return dir
    return 0
  })
})

const visible = computed(() => sorted.value.slice(0, visibleCount.value))
const remaining = computed(() => Math.max(0, sorted.value.length - visibleCount.value))
const totalCount = computed(() => props.files.length)

function toggleSort(field) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value
  } else {
    sortField.value = field
    sortAsc.value = true
  }
}

function loadMore() {
  visibleCount.value += props.pageSize
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
    ', ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

function sortIcon(field) {
  if (sortField.value !== field) return null
  return sortAsc.value ? ChevronUp : ChevronDown
}
</script>

<template>
  <div>
    <!-- Header row -->
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-[14px] font-semibold text-text-heading">
        Files
        <span class="text-text-muted font-normal">({{ totalCount }})</span>
      </h2>
      <input
        v-model="filter"
        type="text"
        placeholder="Filter files..."
        class="w-44 px-3 py-1.5 bg-card-bg border border-border rounded-lg text-[12px] text-text-heading placeholder:text-text-muted focus:outline-none focus:border-accent"
      />
    </div>

    <div v-if="files.length === 0" class="text-center py-10 text-text-muted">
      <FileText :size="32" :stroke-width="1" class="mx-auto mb-2 opacity-40" />
      <p class="text-[13px]">No files uploaded yet</p>
    </div>

    <div v-else-if="filtered.length === 0" class="text-center py-8 text-text-muted">
      <p class="text-[13px]">No files match "{{ filter }}"</p>
    </div>

    <div v-else class="border border-border rounded-xl overflow-hidden bg-card-bg shadow-sm">
      <!-- Column headers -->
      <div class="grid grid-cols-[1fr_80px_140px] gap-2 px-4 py-2 bg-surface text-[11px] font-semibold text-text-muted uppercase tracking-wider border-b border-border">
        <button @click="toggleSort('filename')" class="flex items-center gap-1 text-left cursor-pointer hover:text-text-heading transition-colors">
          Name
          <component v-if="sortIcon('filename')" :is="sortIcon('filename')" :size="12" :stroke-width="2" />
        </button>
        <button @click="toggleSort('size_bytes')" class="flex items-center gap-1 text-right cursor-pointer hover:text-text-heading transition-colors justify-end">
          Size
          <component v-if="sortIcon('size_bytes')" :is="sortIcon('size_bytes')" :size="12" :stroke-width="2" />
        </button>
        <button @click="toggleSort('transferred_at')" class="flex items-center gap-1 text-right cursor-pointer hover:text-text-heading transition-colors justify-end">
          Uploaded
          <component v-if="sortIcon('transferred_at')" :is="sortIcon('transferred_at')" :size="12" :stroke-width="2" />
        </button>
      </div>

      <!-- File rows -->
      <div
        v-for="(file, i) in visible"
        :key="file.id"
        class="grid grid-cols-[1fr_80px_140px] gap-2 px-4 py-2 text-[12px] hover:bg-surface-hover transition-colors"
        :class="i < visible.length - 1 ? 'border-b border-border/50' : ''"
      >
        <div class="flex items-center gap-2 min-w-0">
          <FileText :size="14" :stroke-width="1.5" class="text-text-muted shrink-0" />
          <div class="min-w-0">
            <div class="text-text-heading font-medium truncate">{{ file.filename }}</div>
            <div v-if="file.relative_path" class="text-[11px] text-text-muted truncate">
              {{ file.relative_path }}
            </div>
          </div>
        </div>
        <div class="text-right text-text-muted self-center">{{ formatSize(file.size_bytes) }}</div>
        <div class="text-right text-text-muted self-center">{{ formatDate(file.transferred_at || file.created_at) }}</div>
      </div>

      <!-- Load more -->
      <div v-if="remaining > 0" class="px-4 py-3 border-t border-border text-center">
        <button
          @click="loadMore"
          class="text-[12px] font-medium text-accent hover:text-accent-hover hover:underline cursor-pointer"
        >
          Load more ({{ remaining }} remaining)
        </button>
      </div>
    </div>
  </div>
</template>
