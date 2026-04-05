<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { CheckCircle, XCircle, Loader, Clock, Sparkles, RotateCcw, SearchCheck } from 'lucide-vue-next'
import { useWikisStore } from '../../stores/wikis'

const props = defineProps({
  wikiId: { type: String, required: true },
})

const wikisStore = useWikisStore()

const jobs = ref([])
const showCompleted = ref(false)
const pollInterval = ref(5000)
let timer = null

const INTERVAL_OPTIONS = [
  { label: 'Now', value: 0 },
  { label: '3s', value: 3000 },
  { label: '5s', value: 5000 },
  { label: '10s', value: 10000 },
  { label: '30s', value: 30000 },
]

const runningJobs = computed(() => jobs.value.filter(j => j.status === 'pending' || j.status === 'running'))
const completedJobs = computed(() => jobs.value.filter(j => j.status === 'complete' || j.status === 'failed'))
const hasRunning = computed(() => runningJobs.value.length > 0)

async function fetchJobs() {
  try {
    jobs.value = await wikisStore.listJobs(props.wikiId)
  } catch (e) {
    console.error('Failed to fetch jobs:', e)
  }
}

function startPolling() {
  stopPolling()
  if (pollInterval.value > 0) {
    timer = setInterval(fetchJobs, pollInterval.value)
  }
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function setInterval_(fn, ms) {
  return setInterval(fn, ms)
}

function handleIntervalClick(value) {
  if (value === 0) {
    fetchJobs()
    return
  }
  pollInterval.value = value
}

watch(pollInterval, () => {
  startPolling()
})

watch(hasRunning, (val) => {
  if (!val) stopPolling()
  else startPolling()
})

onMounted(() => {
  fetchJobs()
  if (hasRunning.value) startPolling()
})

onUnmounted(() => {
  stopPolling()
})

function jobIcon(type) {
  if (type === 'compile') return Sparkles
  if (type === 'full_rebuild') return RotateCcw
  if (type === 'lint') return SearchCheck
  return Clock
}

function jobLabel(type) {
  if (type === 'compile') return 'Compile'
  if (type === 'full_rebuild') return 'Full Rebuild'
  if (type === 'lint') return 'Lint'
  return type
}

function statusIcon(status) {
  if (status === 'pending') return Clock
  if (status === 'running') return Loader
  if (status === 'complete') return CheckCircle
  if (status === 'failed') return XCircle
  return Clock
}

function statusColor(status) {
  if (status === 'pending') return 'text-text-muted'
  if (status === 'running') return 'text-accent'
  if (status === 'complete') return 'text-green-600'
  if (status === 'failed') return 'text-red-600'
  return 'text-text-muted'
}

function statusLabel(status) {
  if (status === 'pending') return 'Queued'
  if (status === 'running') return 'Running'
  if (status === 'complete') return 'Complete'
  if (status === 'failed') return 'Failed'
  return status
}

function progressPercent(job) {
  const p = job.result?.progress
  if (!p || !p.total) return 0
  return Math.round((p.current / p.total) * 100)
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  if (diff < 60000) return 'just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return `${Math.floor(diff / 86400000)}d ago`
}

function duration(job) {
  if (!job.started_at) return ''
  const end = job.completed_at ? new Date(job.completed_at) : new Date()
  const secs = Math.round((end - new Date(job.started_at)) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

function usageSummary(job) {
  const u = job.result?.usage
  if (!u) return null
  return u
}

function formatCost(usd) {
  if (usd < 0.01) return `$${(usd * 100).toFixed(2)}¢`
  return `$${usd.toFixed(4)}`
}

function formatTokens(n) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}

function resultSummary(job) {
  if (job.job_type === 'lint' && job.result?.report) {
    const match = job.result.report.match(/(\d+)\/10/)
    return match ? `Health score: ${match[0]}` : 'Report ready'
  }
  if (job.result?.articles_written != null) {
    return `${job.result.articles_written} articles written`
  }
  return ''
}
</script>

<template>
  <div>
    <!-- Header with polling chips -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-[14px] font-semibold text-text-heading">
        Jobs
        <span v-if="hasRunning" class="text-accent font-normal">({{ runningJobs.length }} running)</span>
      </h2>
      <div class="flex items-center gap-1">
        <span class="text-[11px] text-text-muted mr-1">Poll:</span>
        <button
          v-for="opt in INTERVAL_OPTIONS" :key="opt.value"
          @click="handleIntervalClick(opt.value)"
          class="px-2.5 py-1 text-[11px] font-medium rounded-full transition-colors cursor-pointer"
          :class="opt.value === 0
            ? 'text-accent hover:bg-accent-subtle'
            : pollInterval === opt.value
              ? 'bg-accent text-white'
              : 'text-text-muted hover:text-text-heading hover:bg-surface-hover'"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- Running jobs -->
    <div v-if="runningJobs.length === 0 && completedJobs.length === 0" class="text-center py-10 text-text-muted">
      <Clock :size="32" :stroke-width="1" class="mx-auto mb-2 opacity-40" />
      <p class="text-[13px]">No jobs yet. Use Compile or Lint to start one.</p>
    </div>

    <div class="space-y-3">
      <div
        v-for="job in runningJobs" :key="job.job_id"
        class="border border-accent/30 rounded-xl bg-accent-subtle p-4"
      >
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <component :is="statusIcon(job.status)" :size="16" :stroke-width="2" :class="statusColor(job.status)"
              class="animate-spin" />
            <span class="text-[13px] font-semibold text-text-heading">{{ jobLabel(job.job_type) }}</span>
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-accent/10 text-accent font-medium">
              {{ statusLabel(job.status) }}
            </span>
          </div>
          <div class="text-[11px] text-text-muted">
            {{ duration(job) }}
          </div>
        </div>

        <!-- Progress bar -->
        <div v-if="job.result?.progress" class="mt-2">
          <div class="flex items-center justify-between text-[11px] text-text-muted mb-1">
            <span>{{ job.result.progress.message }}</span>
            <span v-if="job.result.progress.total > 0">
              {{ job.result.progress.current }}/{{ job.result.progress.total }}
            </span>
          </div>
          <div class="h-2 bg-white/60 rounded-full overflow-hidden">
            <div
              class="h-full bg-accent rounded-full transition-all duration-500"
              :style="{ width: progressPercent(job) + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Completed jobs toggle -->
    <div v-if="completedJobs.length > 0" class="mt-4">
      <button
        @click="showCompleted = !showCompleted"
        class="text-[12px] font-medium text-text-muted hover:text-text-heading cursor-pointer"
      >
        {{ showCompleted ? 'Hide' : 'Show' }} completed jobs ({{ completedJobs.length }})
      </button>

      <div v-if="showCompleted" class="space-y-2 mt-3">
        <div
          v-for="job in completedJobs" :key="job.job_id"
          class="border border-border rounded-xl p-3"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <component :is="statusIcon(job.status)" :size="14" :stroke-width="2" :class="statusColor(job.status)" />
              <span class="text-[13px] font-medium text-text-heading">{{ jobLabel(job.job_type) }}</span>
              <span class="text-[11px] text-text-muted">{{ resultSummary(job) }}</span>
            </div>
            <div class="flex items-center gap-3 text-[11px] text-text-muted">
              <span v-if="duration(job)">{{ duration(job) }}</span>
              <span>{{ timeAgo(job.completed_at || job.created_at) }}</span>
            </div>
          </div>
          <!-- Usage stats -->
          <div v-if="usageSummary(job)" class="mt-2 flex items-center gap-4 text-[11px] text-text-muted">
            <span>{{ formatTokens(usageSummary(job).total_tokens) }} tokens</span>
            <span>{{ formatCost(usageSummary(job).cost_usd) }}</span>
            <span>{{ usageSummary(job).calls }} LLM calls</span>
            <span v-for="(data, model) in usageSummary(job).by_model" :key="model" class="px-1.5 py-0.5 bg-surface-hover rounded text-[10px]">
              {{ model }}: {{ formatTokens(data.prompt_tokens + data.completion_tokens) }} · {{ formatCost(data.cost_usd) }}
            </span>
          </div>
          <div v-if="job.error" class="mt-2 text-[12px] text-red-600">
            {{ job.error }}
          </div>
          <div v-if="job.job_type === 'lint' && job.result?.report && job.status === 'complete'"
            class="mt-2 text-[12px] text-text-body whitespace-pre-wrap max-h-48 overflow-y-auto bg-surface-hover rounded p-3">
            {{ job.result.report }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
