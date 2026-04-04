<script setup>
import { ref, computed } from 'vue'
import { ChevronDown, ChevronRight, Folder } from 'lucide-vue-next'
import UploadFileRow from './UploadFileRow.vue'

const props = defineProps({
  folder: {
    type: String,
    required: true,
  },
  files: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['retry'])

const expanded = ref(true)

const readyCount = computed(() => {
  return props.files.filter(f => f.status === 'clean').length
})

const totalCount = computed(() => {
  return props.files.length
})

function toggleExpanded() {
  expanded.value = !expanded.value
}

function handleRetry(file) {
  emit('retry', file)
}
</script>

<template>
  <div class="border border-border rounded-lg overflow-hidden card mb-3">
    <button
      @click="toggleExpanded"
      class="w-full flex items-center justify-between px-4 py-2.5 hover:bg-surface-hover transition-colors cursor-pointer text-left"
    >
      <div class="flex items-center gap-2">
        <component
          :is="expanded ? ChevronDown : ChevronRight"
          :size="14"
          :stroke-width="2"
          class="text-text-muted"
        />
        <Folder :size="14" :stroke-width="1.5" class="text-text-muted" />
        <span class="text-[13px] font-medium text-text-heading">{{ folder }}</span>
        <span class="text-[11px] text-text-muted">({{ readyCount }}/{{ totalCount }} ready)</span>
      </div>
      <div class="text-[11px] text-text-muted">
        {{ expanded ? 'Collapse' : 'Expand' }}
      </div>
    </button>

    <div v-if="expanded" class="px-4 pb-2 border-t border-border">
      <UploadFileRow
        v-for="file in files"
        :key="file.fileId"
        :file="file"
        @retry="handleRetry"
      />
    </div>
  </div>
</template>
