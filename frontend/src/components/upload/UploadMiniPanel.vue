<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { ChevronDown, ChevronUp, X, CheckCircle, XCircle, Upload, ShieldAlert, Clock, Loader } from 'lucide-vue-next'
import { useUploadsStore } from '../../stores/uploads'

const uploads = useUploadsStore()

// Panel states: expanded | minimized | dismissed
const panelState = ref('expanded')
let autoDismissTimer = null

const activeBatch = computed(() => uploads.activeBatch)
const progress = computed(() => activeBatch.value ? uploads.overallProgress(activeBatch.value.id) : null)
const isVisible = computed(() => activeBatch.value && panelState.value !== 'dismissed')

const allUploaded = computed(() => {
  if (!progress.value) return false
  return progress.value.uploading === 0 && progress.value.queued === 0
})

const allComplete = computed(() => {
  if (!progress.value) return false
  return progress.value.pending === 0 && allUploaded.value
})

const hasErrors = computed(() => {
  return progress.value?.failed > 0
})

const statusText = computed(() => {
  if (!progress.value) return ''
  const p = progress.value
  if (p.uploading > 0) return `Uploading ${p.complete + p.uploading}/${p.total} files...`
  if (p.pending > 0) return `Scanning ${p.pending} file${p.pending !== 1 ? 's' : ''}...`
  if (p.failed > 0 && p.complete > 0) return `${p.complete} uploaded, ${p.failed} failed`
  if (p.failed > 0) return `${p.failed} file${p.failed !== 1 ? 's' : ''} failed`
  return `${p.complete} file${p.complete !== 1 ? 's' : ''} uploaded`
})

const statusIcon = computed(() => {
  if (!progress.value) return Loader
  if (progress.value.uploading > 0) return Upload
  if (progress.value.pending > 0) return ShieldAlert
  if (allComplete.value && !hasErrors.value) return CheckCircle
  if (hasErrors.value) return XCircle
  return CheckCircle
})

const statusIconColor = computed(() => {
  if (!progress.value) return 'text-text-muted'
  if (progress.value.uploading > 0 || progress.value.pending > 0) return 'text-accent'
  if (allComplete.value && !hasErrors.value) return 'text-green-600'
  if (hasErrors.value) return 'text-red-600'
  return 'text-green-600'
})

const progressPercent = computed(() => {
  if (!progress.value || !progress.value.bytesTotal) return 0
  return Math.round((progress.value.bytesUploaded / progress.value.bytesTotal) * 100)
})

const files = computed(() => {
  if (!activeBatch.value) return []
  return Array.from(activeBatch.value.files.values()).filter(f => f.status !== 'rejected')
})

const rejectedFiles = computed(() => {
  if (!activeBatch.value) return []
  return Array.from(activeBatch.value.files.values()).filter(f => f.status === 'rejected')
})

// Auto-minimize when all uploads done, scanning starts
watch(allUploaded, (val) => {
  if (val && !allComplete.value) {
    panelState.value = 'minimized'
  }
})

// Auto-dismiss 5s after all complete (unless errors)
watch(allComplete, (val) => {
  if (val && !hasErrors.value) {
    autoDismissTimer = setTimeout(() => {
      panelState.value = 'dismissed'
      if (activeBatch.value) {
        uploads.cancelBatch(activeBatch.value.id)
      }
    }, 5000)
  }
})

// Reset state when a new batch appears
watch(() => uploads.activeBatchId, () => {
  panelState.value = 'expanded'
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }
})

onUnmounted(() => {
  if (autoDismissTimer) clearTimeout(autoDismissTimer)
})

function toggle() {
  panelState.value = panelState.value === 'expanded' ? 'minimized' : 'expanded'
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }
}

function dismiss() {
  panelState.value = 'dismissed'
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }
}

function fileStatusIcon(status) {
  switch (status) {
    case 'queued': return Clock
    case 'uploading': return Upload
    case 'pending_scan': return ShieldAlert
    case 'clean': return CheckCircle
    case 'failed_scan': case 'failed_upload': return XCircle
    case 'failed_timeout': return Clock
    default: return Clock
  }
}

function fileStatusColor(status) {
  switch (status) {
    case 'queued': return 'text-text-muted'
    case 'uploading': return 'text-accent'
    case 'pending_scan': return 'text-yellow-600'
    case 'clean': return 'text-green-600'
    case 'failed_scan': case 'failed_upload': return 'text-red-600'
    case 'failed_timeout': return 'text-orange-600'
    default: return 'text-text-muted'
  }
}

function fileStatusLabel(file) {
  switch (file.status) {
    case 'queued': return 'Queued'
    case 'uploading': return `${file.uploadProgress}%`
    case 'pending_scan': return 'Scanning...'
    case 'clean': return 'Done'
    case 'failed_scan': return 'Blocked'
    case 'failed_upload': return 'Failed'
    case 'failed_timeout': return 'Timeout'
    default: return ''
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="isVisible"
      class="fixed bottom-4 right-4 w-80 bg-card-bg border border-border rounded-xl shadow-lg z-50 overflow-hidden"
    >
      <!-- Header bar — always visible -->
      <div
        class="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none"
        :class="allComplete && !hasErrors ? 'bg-green-50' : ''"
        @click="toggle"
      >
        <component :is="statusIcon" :size="16" :stroke-width="2" :class="statusIconColor" />
        <span class="flex-1 text-[13px] font-medium text-text-heading truncate">
          {{ statusText }}
        </span>

        <!-- Progress percentage when uploading -->
        <span
          v-if="progress && (progress.uploading > 0)"
          class="text-[12px] font-medium text-accent"
        >
          {{ progressPercent }}%
        </span>

        <button
          @click.stop="toggle"
          class="p-0.5 rounded hover:bg-surface-hover transition-colors"
        >
          <component :is="panelState === 'expanded' ? ChevronDown : ChevronUp" :size="14" :stroke-width="2" class="text-text-muted" />
        </button>
        <button
          @click.stop="dismiss"
          class="p-0.5 rounded hover:bg-surface-hover transition-colors"
        >
          <X :size="14" :stroke-width="2" class="text-text-muted" />
        </button>
      </div>

      <!-- Progress bar — visible when not complete -->
      <div v-if="!allComplete && progress" class="px-4 pb-1">
        <div class="h-1 bg-surface-hover rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="hasErrors ? 'bg-red-500' : 'bg-accent'"
            :style="{ width: progressPercent + '%' }"
          ></div>
        </div>
      </div>

      <!-- Expanded file list -->
      <div v-if="panelState === 'expanded'" class="max-h-52 overflow-y-auto">
        <div
          v-for="file in files"
          :key="file.fileId"
          class="flex items-center gap-2.5 px-4 py-1.5 text-[12px]"
        >
          <component
            :is="fileStatusIcon(file.status)"
            :size="12"
            :stroke-width="2"
            :class="fileStatusColor(file.status)"
          />
          <span class="flex-1 text-text-heading truncate">{{ file.filename }}</span>

          <!-- Per-file progress bar when uploading -->
          <div v-if="file.status === 'uploading'" class="w-12">
            <div class="h-1 bg-surface-hover rounded-full overflow-hidden">
              <div class="h-full bg-accent rounded-full transition-all duration-300" :style="{ width: file.uploadProgress + '%' }"></div>
            </div>
          </div>

          <span :class="fileStatusColor(file.status)" class="text-[11px] shrink-0">
            {{ fileStatusLabel(file) }}
          </span>
        </div>

        <!-- Rejected files -->
        <div
          v-for="file in rejectedFiles"
          :key="file.fileId"
          class="flex items-center gap-2.5 px-4 py-1.5 text-[12px]"
        >
          <XCircle :size="12" :stroke-width="2" class="text-red-600" />
          <span class="flex-1 text-text-muted truncate line-through">{{ file.filename }}</span>
          <span class="text-red-600 text-[11px] shrink-0 truncate max-w-24">{{ file.rejectReason }}</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
</style>
