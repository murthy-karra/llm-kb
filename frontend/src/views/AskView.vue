<script setup>
import { onMounted, ref } from 'vue'
import { Marked } from 'marked'
import { useKbStore } from '../stores/kb'

const store = useKbStore()
const question = ref('')
const answer = ref('')
const selectedModel = ref('')
const usedModel = ref('')
const timeTaken = ref(0)
const usage = ref(null)

const marked = new Marked()

onMounted(() => {
  store.fetchModels()
})

async function handleAsk() {
  if (!question.value.trim()) return
  answer.value = ''
  usedModel.value = ''
  timeTaken.value = 0
  usage.value = null
  const start = performance.now()
  const result = await store.askQuestion(question.value.trim(), selectedModel.value || null)
  timeTaken.value = ((performance.now() - start) / 1000).toFixed(1)
  answer.value = await marked.parse(result.answer)
  usedModel.value = result.model
  usage.value = {
    prompt: result.prompt_tokens,
    completion: result.completion_tokens,
    total: result.total_tokens,
    cost: result.cost_usd,
  }
}
</script>

<template>
  <div>
    <h1 class="text-[22px] font-semibold text-text-heading tracking-tight">Ask</h1>
    <p class="text-[13px] text-text-muted mt-1 mb-6">Query your knowledge base</p>

    <div class="mb-6">
      <textarea
        v-model="question"
        rows="3"
        placeholder="What would you like to know?"
        class="input w-full resize-none leading-relaxed !rounded-xl !py-3 !px-4"
        @keydown.meta.enter="handleAsk"
      />
      <div class="flex justify-between items-center mt-2.5">
        <div class="flex items-center gap-3">
          <select
            v-model="selectedModel"
            class="input !py-1.5 !px-3 !text-[12px] !rounded-lg appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23A5A09C%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_8px_center] bg-no-repeat pr-7"
          >
            <option value="">Default ({{ store.models[0]?.model || '...' }})</option>
            <option v-for="m in store.models" :key="m.id" :value="m.id">
              {{ m.name }} — {{ m.model }}
            </option>
          </select>
          <span class="text-[11px] text-text-muted font-medium">Cmd+Enter to submit</span>
        </div>
        <button @click="handleAsk" :disabled="store.loading || !question.trim()" class="btn-accent !px-5">
          {{ store.loading ? 'Thinking...' : 'Ask' }}
        </button>
      </div>
    </div>

    <div v-if="answer" class="card p-6">
      <div v-if="usedModel" class="flex items-center gap-2 flex-wrap text-[11px] font-medium text-text-muted mb-4 pb-3 border-b border-border">
        <span>Answered by <span class="text-text-heading">{{ usedModel }}</span></span>
        <span>&middot; {{ timeTaken }}s</span>
        <span v-if="usage">&middot; {{ usage.prompt.toLocaleString() }} in / {{ usage.completion.toLocaleString() }} out ({{ usage.total.toLocaleString() }} tokens)</span>
        <span v-if="usage && usage.cost > 0">&middot; ${{ usage.cost.toFixed(4) }}</span>
        <span v-if="usage && usage.cost === 0" class="text-green-600">free</span>
      </div>
      <div class="prose max-w-none" v-html="answer" />
    </div>
  </div>
</template>
