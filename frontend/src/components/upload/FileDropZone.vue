<script setup>
import { ref } from 'vue'
import { UploadCloud } from 'lucide-vue-next'

const emit = defineEmits(['files-selected'])

const isDragging = ref(false)
const fileInput = ref(null)
const folderInput = ref(null)

function handleDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

async function handleDrop(e) {
  e.preventDefault()
  isDragging.value = false

  const items = []
  const entries = []

  for (const item of e.dataTransfer.items) {
    if (item.kind === 'file') {
      const entry = item.webkitGetAsEntry()
      if (entry) {
        entries.push(entry)
      }
    }
  }

  await walkEntries(entries, items)
  emit('files-selected', items)
}

async function walkEntries(entries, items) {
  for (const entry of entries) {
    if (entry.isFile) {
      const file = await new Promise((resolve) => {
        entry.file(resolve)
      })
      // Set relativePath as directory only (strip filename from fullPath)
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
    // readEntries returns batches — keep reading until empty
    await readAllDirectoryEntries(reader, items)
  }
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  files.forEach(f => {
    if (!f.webkitRelativePath) {
      f.relativePath = ''
    }
  })
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
</script>

<template>
  <div
    class="border-2 border-dashed rounded-lg p-8 text-center transition-colors duration-200 cursor-pointer"
    :class="isDragging ? 'border-accent bg-accent-subtle' : 'border-border hover:border-text-muted hover:bg-surface-hover'"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
    @click="triggerFilePicker"
  >
    <div class="flex flex-col items-center gap-3">
      <div class="w-12 h-12 rounded-full bg-surface-hover flex items-center justify-center"
           :class="isDragging ? 'text-accent' : 'text-text-muted'">
        <UploadCloud :size="24" :stroke-width="1.5" />
      </div>
      <div>
        <p class="text-[13px] font-medium text-text-heading">
          Drag and drop files or folders here
        </p>
        <p class="text-[12px] text-text-muted mt-1">
          or click to browse
        </p>
      </div>
      <button
        type="button"
        @click.stop="triggerFolderPicker"
        class="text-[12px] font-medium text-accent hover:text-accent-hover hover:underline"
      >
        Upload entire folder
      </button>
      <p class="text-[11px] text-text-muted mt-2">
        Max 10MB per file • PDF, DOCX, PPTX, MD, TXT
      </p>
    </div>

    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".pdf,.docx,.pptx,.md,.txt"
      class="hidden"
      @change="handleFileSelect"
    />
    <input
      ref="folderInput"
      type="file"
      webkitdirectory
      class="hidden"
      @change="handleFolderSelect"
    />
  </div>
</template>
