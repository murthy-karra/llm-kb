<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Folder } from 'lucide-vue-next'
import { useWikisStore } from '../stores/wikis'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const wikisStore = useWikisStore()
const auth = useAuthStore()

const showCreateModal = ref(false)
const newWikiName = ref('')
const newWikiDescription = ref('')
const isCreating = ref(false)
const error = ref(null)

const isAdmin = computed(() => auth.user?.role === 'admin')

onMounted(() => {
  wikisStore.fetchWikis()
})

async function handleCreateWiki() {
  if (!newWikiName.value.trim()) return

  isCreating.value = true
  error.value = null

  try {
    const wiki = await wikisStore.createWiki(newWikiName.value, newWikiDescription.value)
    showCreateModal.value = false
    newWikiName.value = ''
    newWikiDescription.value = ''
    router.push(`/wikis/${wiki.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    isCreating.value = false
  }
}

function goToWiki(wikiId) {
  router.push(`/wikis/${wikiId}`)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Wikis</h1>
        <p class="text-[13px] text-text-muted mt-1">Manage your file collections</p>
      </div>
      <button
        v-if="isAdmin"
        @click="showCreateModal = true"
        class="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded hover:bg-accent-hover transition-colors cursor-pointer"
      >
        Create Wiki
      </button>
    </div>

    <div v-if="wikisStore.loading" class="text-center py-12 text-text-muted">
      Loading...
    </div>

    <div v-else-if="wikisStore.wikis.length === 0" class="text-center py-12">
      <Folder :size="48" :stroke-width="1" class="mx-auto text-text-muted mb-4" />
      <p class="text-[13px] text-text-muted mb-4">No wikis created yet</p>
      <button
        v-if="isAdmin"
        @click="showCreateModal = true"
        class="px-4 py-2 text-[13px] font-medium bg-accent text-white rounded hover:bg-accent-hover transition-colors cursor-pointer"
      >
        Create your first wiki
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="wiki in wikisStore.wikis"
        :key="wiki.id"
        @click="goToWiki(wiki.id)"
        class="card p-5 cursor-pointer hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between mb-3">
          <Folder :size="20" :stroke-width="1.5" class="text-accent" />
          <span class="text-[11px] text-text-muted">
            {{ wiki.file_count }} file{{ wiki.file_count !== 1 ? 's' : '' }}
          </span>
        </div>
        <h3 class="text-[15px] font-semibold text-text-heading mb-1">{{ wiki.name }}</h3>
        <p v-if="wiki.description" class="text-[12px] text-text-muted mb-3 line-clamp-2">
          {{ wiki.description }}
        </p>
        <div class="text-[11px] text-text-muted">
          {{ formatSize(wiki.total_size_bytes) }}
        </div>
      </div>
    </div>

    <div
      v-if="showCreateModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showCreateModal = false"
    >
      <div class="bg-card-bg rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 class="text-[16px] font-semibold text-text-heading mb-4">Create Wiki</h2>

        <div class="space-y-4">
          <div>
            <label class="block text-[12px] font-medium text-text-heading mb-1">Name</label>
            <input
              v-model="newWikiName"
              type="text"
              maxlength="100"
              placeholder="My Wiki"
              class="w-full px-3 py-2 bg-card-bg border border-border rounded text-[13px] text-text-heading placeholder:text-text-muted focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label class="block text-[12px] font-medium text-text-heading mb-1">Description (optional)</label>
            <textarea
              v-model="newWikiDescription"
              rows="3"
              placeholder="What's this wiki for?"
              class="w-full px-3 py-2 bg-card-bg border border-border rounded text-[13px] text-text-heading placeholder:text-text-muted focus:outline-none focus:border-accent resize-none"
            ></textarea>
          </div>

          <div v-if="error" class="text-[12px] text-red-600">
            {{ error }}
          </div>

          <div class="flex gap-3 pt-2">
            <button
              @click="showCreateModal = false"
              class="flex-1 px-4 py-2 text-[13px] font-medium text-text-heading border border-border rounded hover:bg-surface-hover transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              @click="handleCreateWiki"
              :disabled="isCreating || !newWikiName.trim()"
              class="flex-1 px-4 py-2 text-[13px] font-medium bg-accent text-white rounded hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isCreating ? 'Creating...' : 'Create' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
