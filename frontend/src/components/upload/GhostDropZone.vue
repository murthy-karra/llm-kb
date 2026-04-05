<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { UploadCloud } from 'lucide-vue-next'

const emit = defineEmits(['files-selected'])

const isDragging = ref(false)
const fileInput = ref(null)
const folderInput = ref(null)
let dragCounter = 0

function onDragEnter(e) {
  e.preventDefault()
  dragCounter++
  if (dragCounter === 1) isDragging.value = true
}

function onDragLeave(e) {
  e.preventDefault()
  dragCounter--
  if (dragCounter === 0) isDragging.value = false
}

function onDragOver(e) {
  e.preventDefault()
}

async function onDrop(e) {
  e.preventDefault()
  isDragging.value = false
  dragCounter = 0

  const items = []
  const entries = []

  for (const item of e.dataTransfer.items) {
    if (item.kind === 'file') {
      const entry = item.webkitGetAsEntry()
      if (entry) entries.push(entry)
    }
  }

  await walkEntries(entries, items)
  if (items.length > 0) emit('files-selected', items)
}

async function walkEntries(entries, items) {
  for (const entry of entries) {
    if (entry.isFile) {
      const file = await new Promise((resolve) => entry.file(resolve))
      const pathParts = entry.fullPath.replace(/^\//, '').split('/')
      file.relativePath = pathParts.slice(0, -1).join('/')
      items.push(file)
    } else if (entry.isDirectory) {
      const reader = entry.createReader()
      await readAllDirectoryEntries(reader, items)
    }
  }
}

async function readAllDirectoryEntries(reader, items) {
  const entries = await new Promise((resolve) => reader.readEntries(resolve))
  if (entries.length > 0) {
    await walkEntries(entries, items)
    await readAllDirectoryEntries(reader, items)
  }
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  files.forEach(f => { if (!f.webkitRelativePath) f.relativePath = '' })
  emit('files-selected', files)
  fileInput.value.value = ''
}

function handleFolderSelect(e) {
  const files = Array.from(e.target.files)
  emit('files-selected', files)
  folderInput.value.value = ''
}

function triggerFilePicker() {
  fileInput.value?.click()
}

function triggerFolderPicker() {
  folderInput.value?.click()
}

onMounted(() => {
  document.addEventListener('dragenter', onDragEnter)
  document.addEventListener('dragleave', onDragLeave)
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('drop', onDrop)
})

onUnmounted(() => {
  document.removeEventListener('dragenter', onDragEnter)
  document.removeEventListener('dragleave', onDragLeave)
  document.removeEventListener('dragover', onDragOver)
  document.removeEventListener('drop', onDrop)
})

defineExpose({ triggerFilePicker, triggerFolderPicker })
</script>

<template>
  <!-- Full-page drag overlay -->
  <Transition name="fade">
    <div
      v-if="isDragging"
      class="fixed inset-0 z-40 bg-accent/5 backdrop-blur-[2px] flex items-center justify-center"
    >
      <div class="bg-card-bg border-2 border-dashed border-accent rounded-2xl px-16 py-12 text-center shadow-lg">
        <UploadCloud :size="40" :stroke-width="1.5" class="mx-auto text-accent mb-3" />
        <p class="text-[15px] font-semibold text-text-heading">Drop files to upload</p>
        <p class="text-[12px] text-text-muted mt-1">PDF, DOCX, PPTX, MD, TXT • Max 10 MB</p>
      </div>
    </div>
  </Transition>

  <!-- Hidden file inputs -->
  <input ref="fileInput" type="file" multiple accept=".pdf,.docx,.pptx,.md,.txt" class="hidden" @change="handleFileSelect" />
  <input ref="folderInput" type="file" webkitdirectory class="hidden" @change="handleFolderSelect" />
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
