<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWikisStore } from '../stores/wikis'
import { useUploadsStore } from '../stores/uploads'
import FileDropZone from '../components/upload/FileDropZone.vue'
import UploadDrawer from '../components/upload/UploadDrawer.vue'

const route = useRoute()
const router = useRouter()
const wikisStore = useWikisStore()
const uploads = useUploadsStore()

const wikiId = computed(() => route.params.id)
const files = ref([])
const loading = ref(true)
const error = ref(null)

const wiki = computed(() => wikisStore.currentWiki)

onMounted(async () => {
  await loadWiki()
})

async function loadWiki() {
  loading.value = true
  error.value = null

  try {
    await wikisStore.fetchWiki(wikiId.value)
    files.value = await wikisStore.fetchWikiFiles(wikiId.value)
  } catch (e) {
    error.value = e.message
    if (e.message?.includes('404')) {
      router.push('/wikis')
    }
  } finally {
    loading.value = false
  }
}

function handleFilesSelected(fileList) {
  uploads.addFiles(wikiId.value, fileList)
  uploads.startUpload(uploads.activeBatchId)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString()
}

function groupFilesByPath(files) {
  const groups = {}
  files.forEach(file => {
    const parts = file.relative_path.split('/').filter(Boolean)
    const folder = parts[0] || 'Root'
    if (!groups[folder]) {
      groups[folder] = []
    }
    groups[folder].push(file)
  })
  return groups
}

const groupedFiles = computed(() => groupFilesByPath(files.value))

async function handleRefresh() {
  await loadWiki()
}
</script>

<template>
  <div>
    <div v-if="loading" class="text-center py-12 text-text-muted">
      Loading wiki...
    </div>

    <div v-else-if="error" class="text-center py-12">
      <p class="text-red-600 mb-4">{{ error }}</p>
      <button
        @click="handleRefresh"
        class="px-4 py-2 text-[13px] font-medium text-accent hover:underline cursor-pointer"
      >
        Try again
      </button>
    </div>

    <div v-else-if="wiki">
      <div class="mb-6">
        <div class="flex items-start justify-between mb-2">
          <div>
            <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">{{ wiki.name }}</h1>
            <p v-if="wiki.description" class="text-[13px] text-text-muted mt-1">
              {{ wiki.description }}
            </p>
          </div>
          <button
            @click="handleRefresh"
            class="px-3 py-1.5 text-[12px] font-medium text-text-muted hover:text-accent hover:bg-accent-subtle rounded transition-colors cursor-pointer"
          >
            Refresh
          </button>
        </div>
        <div class="flex items-center gap-4 text-[12px] text-text-muted">
          <span>{{ wiki.file_count }} file{{ wiki.file_count !== 1 ? 's' : '' }}</span>
          <span>{{ formatSize(wiki.total_size_bytes) }}</span>
          <span>Created {{ formatDate(wiki.created_at) }}</span>
        </div>
      </div>

      <div class="mb-6 pb-6 border-b border-border">
        <h2 class="text-[14px] font-semibold text-text-heading mb-3">Upload Files</h2>
        <FileDropZone @files-selected="handleFilesSelected" />
      </div>

      <div>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-[14px] font-semibold text-text-heading">Files</h2>
          <span class="text-[12px] text-text-muted">{{ files.length }} file{{ files.length !== 1 ? 's' : '' }}</span>
        </div>

        <div v-if="files.length === 0" class="text-center py-8 text-text-muted">
          <p class="text-[13px]">No files uploaded yet</p>
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="(folderFiles, folder) in groupedFiles"
            :key="folder"
            class="border border-border rounded-lg overflow-hidden card"
          >
            <div class="px-4 py-2 bg-surface-hover border-b border-border">
              <div class="flex items-center gap-2">
                <FolderIcon :size="14" :stroke-width="1.5" class="text-text-muted" />
                <span class="text-[13px] font-medium text-text-heading">{{ folder }}</span>
                <span class="text-[11px] text-text-muted">({{ folderFiles.length }})</span>
              </div>
            </div>
            <div class="divide-y divide-border">
              <div
                v-for="file in folderFiles"
                :key="file.id"
                class="px-4 py-2.5 flex items-center gap-3 hover:bg-surface-hover transition-colors"
              >
                <FileIcon :size="14" :stroke-width="1.5" class="text-text-muted" />
                <div class="flex-1 min-w-0">
                  <div class="text-[13px] font-medium text-text-heading truncate">{{ file.filename }}</div>
                  <div v-if="file.relative_path" class="text-[11px] text-text-muted truncate">
                    {{ file.relative_path }}
                  </div>
                </div>
                <div class="text-right shrink-0">
                  <div class="text-[12px] text-text-muted">{{ formatSize(file.size_bytes) }}</div>
                  <div class="text-[10px] text-text-muted text-right">
                    {{ formatDate(file.transferred_at || file.created_at) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <UploadDrawer :wiki-name="wiki?.name || ''" />
  </div>
</template>

<script>
import { Folder, File as FileIcon } from 'lucide-vue-next'
export default {
  components: { FolderIcon: Folder, FileIcon }
}
</script>