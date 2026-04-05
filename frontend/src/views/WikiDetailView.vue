<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Upload, FolderUp, RefreshCw, Sparkles, RotateCcw, SearchCheck, FileText, BookOpen, MessageCircle, Send, ListTodo, Settings } from 'lucide-vue-next'
import { marked } from 'marked'
import { useWikisStore } from '../stores/wikis'
import { useUploadsStore } from '../stores/uploads'
import { useAuthStore } from '../stores/auth'
import GhostDropZone from '../components/upload/GhostDropZone.vue'
import FileTable from '../components/wiki/FileTable.vue'
import JobsTab from '../components/wiki/JobsTab.vue'

const route = useRoute()
const router = useRouter()
const wikisStore = useWikisStore()
const uploads = useUploadsStore()
const auth = useAuthStore()
const dropZone = ref(null)

const wikiId = computed(() => route.params.id)
const files = ref([])
const articles = ref([])
const loading = ref(true)
const error = ref(null)
const activeTab = ref('files')

// Compile/lint state
const compiling = ref(false)
const linting = ref(false)
const actionResult = ref(null)

// Q&A state
const question = ref('')
const asking = ref(false)
const answer = ref(null)
const answerUsage = ref(null)

// Article detail state
const selectedArticle = ref(null)
const articleLoading = ref(false)

// Model settings
const showSettings = ref(false)
const MODEL_OPTIONS = [
  { value: 'cerebras', label: 'Cerebras (fast)' },
  { value: 'groq', label: 'Groq (fast/cheap)' },
  { value: 'openai', label: 'GPT-5.4 (best)' },
  { value: 'openai-mini', label: 'GPT-5.4 Mini' },
  { value: 'gemini', label: 'Gemini Flash' },
]

const wiki = computed(() => wikisStore.currentWiki)
const isAdmin = computed(() => auth.user?.role === 'admin')

const groupedArticles = computed(() => {
  const groups = {}
  for (const a of articles.value) {
    const cat = a.category || 'general'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(a)
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
})

onMounted(async () => {
  await loadWiki()
})

async function loadWiki() {
  loading.value = true
  error.value = null

  try {
    await wikisStore.fetchWiki(wikiId.value)
    files.value = await wikisStore.fetchWikiFiles(wikiId.value)
    articles.value = await wikisStore.fetchArticles(wikiId.value)
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

async function handleCompile(full = false) {
  compiling.value = true
  try {
    await wikisStore.compileWiki(wikiId.value, full)
    activeTab.value = 'jobs'
  } catch (e) {
    actionResult.value = { type: 'error', message: e.message }
  } finally {
    compiling.value = false
  }
}

async function handleLint() {
  linting.value = true
  try {
    await wikisStore.lintWiki(wikiId.value)
    activeTab.value = 'jobs'
  } catch (e) {
    actionResult.value = { type: 'error', message: e.message }
  } finally {
    linting.value = false
  }
}

async function saveModelSetting(field, value) {
  try {
    await wikisStore.updateWiki(wikiId.value, { [field]: value })
  } catch (e) {
    console.error('Failed to update model:', e)
  }
}

async function openArticle(slug) {
  articleLoading.value = true
  try {
    selectedArticle.value = await wikisStore.fetchArticle(wikiId.value, slug)
  } catch (e) {
    selectedArticle.value = null
  } finally {
    articleLoading.value = false
  }
}

function closeArticle() {
  selectedArticle.value = null
}

async function handleAsk() {
  if (!question.value.trim()) return
  asking.value = true
  answer.value = null
  answerUsage.value = null
  try {
    const result = await wikisStore.askWiki(wikiId.value, question.value)
    answer.value = result.answer
    answerUsage.value = result.usage
  } catch (e) {
    answer.value = `Error: ${e.message}`
  } finally {
    asking.value = false
  }
}

function renderMarkdown(text) {
  return marked(text || '')
}

function dismissResult() {
  actionResult.value = null
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
</script>

<template>
  <div>
    <div v-if="loading" class="text-center py-12 text-text-muted">Loading wiki...</div>

    <div v-else-if="error" class="text-center py-12">
      <p class="text-red-600 mb-4">{{ error }}</p>
      <button @click="loadWiki" class="text-[13px] font-medium text-accent hover:underline cursor-pointer">Try again</button>
    </div>

    <div v-else-if="wiki">
      <!-- Header -->
      <div class="flex items-start justify-between mb-4">
        <div>
          <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">{{ wiki.name }}</h1>
          <p v-if="wiki.description" class="text-[13px] text-text-muted mt-1">{{ wiki.description }}</p>
          <div class="flex items-center gap-4 text-[12px] text-text-muted mt-2">
            <span>{{ wiki.file_count }} source file{{ wiki.file_count !== 1 ? 's' : '' }}</span>
            <span>{{ articles.length }} article{{ articles.length !== 1 ? 's' : '' }}</span>
            <span>{{ formatSize(wiki.total_size_bytes) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button @click="dropZone?.triggerFolderPicker()" class="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-text-muted hover:text-text-heading border border-border rounded-lg hover:bg-surface-hover transition-colors cursor-pointer">
            <FolderUp :size="14" :stroke-width="2" /> Folder
          </button>
          <button @click="dropZone?.triggerFilePicker()" class="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors cursor-pointer">
            <Upload :size="14" :stroke-width="2" /> Upload
          </button>
          <button @click="loadWiki" class="p-1.5 text-text-muted hover:text-accent hover:bg-accent-subtle rounded-lg transition-colors cursor-pointer">
            <RefreshCw :size="14" :stroke-width="2" />
          </button>
          <button v-if="isAdmin" @click="showSettings = !showSettings" class="p-1.5 text-text-muted hover:text-accent hover:bg-accent-subtle rounded-lg transition-colors cursor-pointer" :class="showSettings ? 'text-accent bg-accent-subtle' : ''">
            <Settings :size="14" :stroke-width="2" />
          </button>
        </div>
      </div>

      <!-- Model settings (collapsible) -->
      <div v-if="showSettings && isAdmin" class="mb-4 p-4 border border-border rounded-xl bg-surface">
        <h3 class="text-[12px] font-semibold text-text-heading mb-3 uppercase tracking-wider">LLM Models</h3>
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="block text-[11px] font-medium text-text-muted mb-1">Compile (bulk draft)</label>
            <select
              :value="wiki.compile_model"
              @change="saveModelSetting('compile_model', $event.target.value)"
              class="w-full px-2.5 py-1.5 bg-card-bg border border-border rounded-lg text-[12px] text-text-heading focus:outline-none focus:border-accent cursor-pointer"
            >
              <option v-for="opt in MODEL_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-medium text-text-muted mb-1">Polish (refine)</label>
            <select
              :value="wiki.polish_model"
              @change="saveModelSetting('polish_model', $event.target.value)"
              class="w-full px-2.5 py-1.5 bg-card-bg border border-border rounded-lg text-[12px] text-text-heading focus:outline-none focus:border-accent cursor-pointer"
            >
              <option v-for="opt in MODEL_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-medium text-text-muted mb-1">Q&A (answer questions)</label>
            <select
              :value="wiki.qa_model"
              @change="saveModelSetting('qa_model', $event.target.value)"
              class="w-full px-2.5 py-1.5 bg-card-bg border border-border rounded-lg text-[12px] text-text-heading focus:outline-none focus:border-accent cursor-pointer"
            >
              <option v-for="opt in MODEL_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Action bar (admin) -->
      <div v-if="isAdmin" class="flex items-center gap-2 mb-4">
        <button @click="handleCompile(false)" :disabled="compiling || linting || wiki.file_count === 0"
          class="flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm">
          <Sparkles :size="16" :stroke-width="2" /> {{ compiling ? 'Compiling...' : 'Compile' }}
        </button>
        <button @click="handleCompile(true)" :disabled="compiling || linting || wiki.file_count === 0"
          class="flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm">
          <RotateCcw :size="16" :stroke-width="2" /> {{ compiling ? 'Rebuilding...' : 'Full Rebuild' }}
        </button>
        <button @click="handleLint" :disabled="compiling || linting || articles.length === 0"
          class="flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm">
          <SearchCheck :size="16" :stroke-width="2" /> {{ linting ? 'Linting...' : 'Lint' }}
        </button>
        <span v-if="compiling || linting" class="text-[11px] text-text-muted ml-2">This may take a few minutes...</span>
      </div>

      <!-- Error banner -->
      <div v-if="actionResult" class="mb-4 px-4 py-3 rounded-lg text-[13px] bg-red-50 text-red-800 border border-red-200">
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ actionResult.message }}</span>
          <button @click="dismissResult" class="text-[11px] opacity-60 hover:opacity-100 cursor-pointer ml-4">Dismiss</button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex items-center gap-1 border-b border-border mb-5">
        <button v-for="tab in [
          { key: 'files', label: 'Source Files', icon: FileText, count: files.length },
          { key: 'articles', label: 'Articles', icon: BookOpen, count: articles.length },
          { key: 'ask', label: 'Ask', icon: MessageCircle },
          { key: 'jobs', label: 'Jobs', icon: ListTodo },
        ]" :key="tab.key"
          @click="activeTab = tab.key; selectedArticle = null"
          class="flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium transition-colors cursor-pointer -mb-px border-b-2"
          :class="activeTab === tab.key
            ? 'text-accent border-accent'
            : 'text-text-muted border-transparent hover:text-text-heading hover:border-border'"
        >
          <component :is="tab.icon" :size="14" :stroke-width="2" />
          {{ tab.label }}
          <span v-if="tab.count != null" class="text-[11px] text-text-muted ml-0.5">({{ tab.count }})</span>
        </button>
      </div>

      <!-- Tab: Source Files -->
      <div v-if="activeTab === 'files'">
        <FileTable :files="files" />
      </div>

      <!-- Tab: Articles -->
      <div v-if="activeTab === 'articles'">
        <!-- Article detail view -->
        <div v-if="selectedArticle">
          <button @click="closeArticle" class="text-[12px] font-medium text-accent hover:underline cursor-pointer mb-4">&larr; Back to articles</button>
          <article class="prose">
            <h1>{{ selectedArticle.title }}</h1>
            <div class="flex items-center gap-3 text-[11px] text-text-muted mb-4 -mt-2">
              <span class="px-2 py-0.5 bg-surface-hover rounded text-[11px]">{{ selectedArticle.category }}</span>
              <span v-for="tag in selectedArticle.tags" :key="tag" class="px-2 py-0.5 bg-accent-subtle text-accent rounded text-[11px]">{{ tag }}</span>
            </div>
            <div v-html="renderMarkdown(selectedArticle.content)"></div>
          </article>
        </div>

        <!-- Article list -->
        <div v-else-if="articles.length === 0" class="text-center py-10 text-text-muted">
          <BookOpen :size="32" :stroke-width="1" class="mx-auto mb-2 opacity-40" />
          <p class="text-[13px]">No articles yet. Compile to generate articles from source files.</p>
        </div>

        <div v-else>
          <div v-for="[category, catArticles] in groupedArticles" :key="category" class="mb-5">
            <h3 class="text-[11px] font-semibold text-accent uppercase tracking-wider mb-2 px-1">
              {{ category.replace(/-/g, ' ') }}
            </h3>
            <div class="border border-border rounded-xl overflow-hidden bg-card-bg shadow-sm">
              <button
                v-for="(article, i) in catArticles" :key="article.slug"
                @click="openArticle(article.slug)"
                class="w-full text-left px-4 py-3 hover:bg-surface-hover transition-colors cursor-pointer"
                :class="i < catArticles.length - 1 ? 'border-b border-border/50' : ''"
              >
                <div class="text-[13px] font-medium text-text-heading">{{ article.title }}</div>
                <div class="text-[12px] text-text-muted mt-0.5 line-clamp-1">{{ article.preview }}</div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Ask -->
      <div v-if="activeTab === 'ask'">
        <div v-if="articles.length === 0" class="text-center py-10 text-text-muted">
          <MessageCircle :size="32" :stroke-width="1" class="mx-auto mb-2 opacity-40" />
          <p class="text-[13px]">Compile your wiki first to enable Q&A.</p>
        </div>

        <div v-else>
          <div class="flex gap-2 mb-6">
            <input
              v-model="question"
              @keydown.enter="handleAsk"
              type="text"
              placeholder="Ask a question about this wiki..."
              :disabled="asking"
              class="flex-1 px-4 py-2.5 bg-card-bg border border-border rounded-lg text-[13px] text-text-heading placeholder:text-text-muted focus:outline-none focus:border-accent disabled:opacity-50"
            />
            <button
              @click="handleAsk"
              :disabled="asking || !question.trim()"
              class="flex items-center gap-1.5 px-5 py-2.5 text-[13px] font-semibold bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send :size="14" :stroke-width="2" />
              {{ asking ? 'Thinking...' : 'Ask' }}
            </button>
          </div>

          <div v-if="answer" class="card p-5">
            <div class="prose text-[13px]" v-html="renderMarkdown(answer)"></div>
            <div v-if="answerUsage" class="mt-4 pt-3 border-t border-border flex items-center gap-4 text-[11px] text-text-muted">
              <span>{{ answerUsage.model }}</span>
              <span>{{ (answerUsage.prompt_tokens + answerUsage.completion_tokens).toLocaleString() }} tokens</span>
              <span>${{ answerUsage.cost_usd.toFixed(4) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Jobs -->
      <div v-if="activeTab === 'jobs'">
        <JobsTab :wiki-id="wikiId" />
      </div>
    </div>

    <GhostDropZone ref="dropZone" @files-selected="handleFilesSelected" />
  </div>
</template>
