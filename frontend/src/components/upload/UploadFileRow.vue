<script setup>
import { computed } from 'vue'
import { File, Clock, Upload, ShieldAlert, CheckCircle, XCircle, X } from 'lucide-vue-next'

const props = defineProps({
  file: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['retry'])

const statusIcon = computed(() => {
  switch (props.file.status) {
    case 'queued': return Clock
    case 'uploading': return Upload
    case 'pending_scan': return ShieldAlert
    case 'clean': return CheckCircle
    case 'failed_scan': return XCircle
    case 'failed_timeout': return Clock
    case 'failed_upload': return XCircle
    case 'rejected': return X
    default: return File
  }
})

const statusLabel = computed(() => {
  switch (props.file.status) {
    case 'queued': return 'Queued'
    case 'uploading': return `Uploading ${props.file.uploadProgress}%`
    case 'pending_scan': return 'Scanning...'
    case 'clean': return 'Clean'
    case 'failed_scan': return 'Malware detected'
    case 'failed_timeout': return 'Scan timeout'
    case 'failed_upload': return 'Upload failed'
    case 'rejected': return 'Rejected'
    default: return 'Unknown'
  }
})

const statusColor = computed(() => {
  switch (props.file.status) {
    case 'queued': return 'text-text-muted'
    case 'uploading': return 'text-accent'
    case 'pending_scan': return 'text-text-muted'
    case 'clean': return 'text-green-600'
    case 'failed_scan': return 'text-red-600'
    case 'failed_timeout': return 'text-orange-600'
    case 'failed_upload': return 'text-red-600'
    case 'rejected': return 'text-red-600'
    default: return 'text-text-muted'
  }
})

const canRetry = computed(() => {
  return props.file.status.startsWith('failed')
})

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function handleRetry() {
  emit('retry', props.file)
}
</script>

<template>
  <div class="flex items-center gap-3 py-2 text-[12px]">
    <div :class="statusColor">
      <component :is="statusIcon" :size="14" :stroke-width="2" />
    </div>

    <div class="flex-1 min-w-0">
      <div class="font-medium text-text-heading truncate">{{ file.filename }}</div>
      <div class="text-text-muted">{{ formatSize(file.sizeBytes) }}</div>
    </div>

    <div class="w-24 text-right shrink-0">
      <span :class="statusColor">{{ statusLabel }}</span>
    </div>

    <div v-if="file.status === 'uploading'" class="w-20 shrink-0">
      <div class="h-1.5 bg-surface-hover rounded-full overflow-hidden">
        <div class="h-full bg-accent transition-all duration-300" :style="{ width: file.uploadProgress + '%' }"></div>
      </div>
    </div>

    <div v-if="file.rejectReason" class="w-32 shrink-0 text-red-600 truncate">
      {{ file.rejectReason }}
    </div>

    <button
      v-if="canRetry"
      @click="handleRetry"
      class="shrink-0 px-2 py-1 text-[11px] font-medium text-accent hover:text-accent-hover hover:bg-accent-subtle rounded transition-colors cursor-pointer"
    >
      Retry
    </button>
  </div>
</template>
