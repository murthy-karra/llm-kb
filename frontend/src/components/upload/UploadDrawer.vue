<script setup>
import { computed, ref } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useUploadsStore } from '../../stores/uploads'
import UploadFolderGroup from './UploadFolderGroup.vue'
import UploadFileRow from './UploadFileRow.vue'

const props = defineProps({
  wikiName: {
    type: String,
    default: '',
  },
})

const uploads = useUploadsStore()
const collapsed = ref(false)

const activeBatch = computed(() => uploads.activeBatch)
const progress = computed(() => activeBatch.value ? uploads.overallProgress(activeBatch.value.id) : null)

const rejectedFiles = computed(() => {
  if (!activeBatch.value) return []
  return Array.from(activeBatch.value.files.values()).filter(f => f.status === 'rejected')
})

const folderGroups = computed(() => {
  if (!activeBatch.value) return {}
  return uploads.filesByFolder(activeBatch.value.id)
})

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function handleCancelBatch() {
  if (activeBatch.value) {
    uploads.cancelBatch(activeBatch.value.id)
  }
}

function handleRetryFile(file) {
  if (activeBatch.value) {
    uploads.retryFile(activeBatch.value.id, file.fileId)
  }
}
</script>

<template>
  <div v-if="activeBatch" class="fixed bottom-0 right-0 left-0 bg-card-bg border-t border-border shadow-lg z-50">
    <div class="max-w-2xl mx-auto">
      <div class="px-6 py-4 border-b border-border flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button
            @click="collapsed = !collapsed"
            class="p-1 rounded hover:bg-surface-hover transition-colors cursor-pointer"
          >
            <component :is="collapsed ? ChevronUp : ChevronDown" :size="16" :stroke-width="2" class="text-text-muted" />
          </button>
          <div>
            <h3 class="text-[14px] font-semibold text-text-heading">Upload to "{{ wikiName || 'Wiki' }}"</h3>
            <p class="text-[12px] text-text-muted mt-0.5">
              {{ progress?.complete || 0 }}/{{ progress?.total || 0 }} files
            </p>
          </div>
        </div>
        <button
          @click="handleCancelBatch"
          class="px-3 py-1.5 text-[12px] font-medium text-text-muted hover:text-red-600 hover:bg-red-50 rounded transition-colors cursor-pointer"
        >
          Cancel
        </button>
      </div>

      <div v-if="!collapsed" class="px-6 py-3">
        <div v-if="progress" class="mb-4">
          <div class="flex items-center justify-between text-[12px] text-text-muted mb-1.5">
            <span>{{ formatBytes(progress.bytesUploaded) }} / {{ formatBytes(progress.bytesTotal) }}</span>
            <span>{{ ((progress.bytesUploaded / (progress.bytesTotal || 1)) * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-2 bg-surface-hover rounded-full overflow-hidden">
            <div
              class="h-full bg-accent transition-all duration-300"
              :style="{ width: ((progress.bytesUploaded / (progress.bytesTotal || 1)) * 100) + '%' }"
            ></div>
          </div>
        </div>

        <div class="max-h-64 overflow-y-auto space-y-1">
          <UploadFolderGroup
            v-for="(group, folder) in folderGroups"
            :key="folder"
            :folder="folder"
            :files="group.files"
            @retry="handleRetryFile"
          />

          <div v-if="rejectedFiles.length > 0" class="border border-border rounded-lg overflow-hidden card">
            <div class="px-4 py-2 bg-red-50 border-b border-border">
              <span class="text-[11px] font-semibold text-red-600">
                {{ rejectedFiles.length }} file{{ rejectedFiles.length !== 1 ? 's' : '' }} with errors
              </span>
            </div>
            <div class="px-4 py-2">
              <UploadFileRow
                v-for="file in rejectedFiles"
                :key="file.fileId"
                :file="file"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
