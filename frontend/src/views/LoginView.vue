<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen">
    <!-- Left: Green branding panel -->
    <div class="hidden lg:flex w-1/2 bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-700 relative overflow-hidden">
      <!-- Decorative circles -->
      <div class="absolute -top-20 -left-20 w-80 h-80 bg-white/5 rounded-full"></div>
      <div class="absolute bottom-10 right-10 w-60 h-60 bg-white/3 rounded-full"></div>
      <div class="absolute top-1/3 right-1/4 w-40 h-40 bg-white/4 rounded-full"></div>
      <!-- Subtle grid overlay -->
      <div class="absolute inset-0 opacity-[0.03]" style="background-image: url('data:image/svg+xml,%3Csvg width=&quot;40&quot; height=&quot;40&quot; xmlns=&quot;http://www.w3.org/2000/svg&quot;%3E%3Cpath d=&quot;M0 0h40v40H0z&quot; fill=&quot;none&quot; stroke=&quot;white&quot; stroke-width=&quot;0.5&quot;/%3E%3C/svg%3E');"></div>

      <div class="relative z-10 flex flex-col justify-center px-16">
        <div class="mb-8">
          <!-- Logo: brain-circuit merged with open book / wiki nodes -->
          <svg width="72" height="72" viewBox="0 0 72 72" fill="none" class="mb-6 drop-shadow-lg">
            <!-- Book base -->
            <rect x="8" y="16" width="56" height="44" rx="4" stroke="white" stroke-width="2" fill="white" fill-opacity="0.06"/>
            <line x1="36" y1="16" x2="36" y2="60" stroke="white" stroke-width="1.5" opacity="0.3"/>
            <!-- Neural/AI network nodes on left page -->
            <circle cx="20" cy="30" r="3" fill="white" fill-opacity="0.9"/>
            <circle cx="28" cy="42" r="3" fill="white" fill-opacity="0.9"/>
            <circle cx="18" cy="50" r="2.5" fill="white" fill-opacity="0.6"/>
            <circle cx="30" cy="32" r="2" fill="white" fill-opacity="0.5"/>
            <line x1="20" y1="30" x2="28" y2="42" stroke="white" stroke-width="1" opacity="0.5"/>
            <line x1="20" y1="30" x2="30" y2="32" stroke="white" stroke-width="1" opacity="0.4"/>
            <line x1="28" y1="42" x2="18" y2="50" stroke="white" stroke-width="1" opacity="0.4"/>
            <!-- "LLM" text on right page -->
            <text x="44" y="35" font-family="Inter, sans-serif" font-size="10" font-weight="700" fill="white" fill-opacity="0.9">LLM</text>
            <!-- Wiki link arrows on right page -->
            <line x1="42" y1="42" x2="56" y2="42" stroke="white" stroke-width="1" opacity="0.4"/>
            <line x1="42" y1="47" x2="52" y2="47" stroke="white" stroke-width="1" opacity="0.3"/>
            <line x1="42" y1="52" x2="58" y2="52" stroke="white" stroke-width="1" opacity="0.25"/>
            <!-- AI sparkle -->
            <path d="M56 22l1.5 3 3 1.5-3 1.5-1.5 3-1.5-3-3-1.5 3-1.5z" fill="white" fill-opacity="0.7"/>
            <path d="M14 24l1 2 2 1-2 1-1 2-1-2-2-1 2-1z" fill="white" fill-opacity="0.4"/>
          </svg>
          <h1 class="text-4xl font-bold text-white tracking-tight leading-tight">
            LLM<br/>Knowledge Base
          </h1>
        </div>
        <p class="text-emerald-200 text-lg leading-relaxed max-w-md">
          Ingest, compile, and query your documents with AI. Turn raw sources into a structured, searchable wiki.
        </p>
        <div class="mt-12 flex gap-6 text-emerald-300 text-sm">
          <div>
            <div class="text-2xl font-bold text-white">31</div>
            <div>Articles</div>
          </div>
          <div class="w-px bg-white/20"></div>
          <div>
            <div class="text-2xl font-bold text-white">13</div>
            <div>Sources</div>
          </div>
          <div class="w-px bg-white/20"></div>
          <div>
            <div class="text-2xl font-bold text-white">5</div>
            <div>Models</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Login form -->
    <div class="flex-1 flex items-center justify-center bg-page-bg px-6">
      <div class="w-full max-w-sm">
        <!-- Mobile logo -->
        <div class="lg:hidden mb-8 text-center">
          <h1 class="text-2xl font-bold text-text-heading">LLM Knowledge Base</h1>
          <p class="text-sm text-text-muted mt-1">Sign in to continue</p>
        </div>

        <!-- Form card -->
        <div class="bg-card-bg rounded-2xl border border-border p-8 shadow-lg">
          <h2 class="text-xl font-semibold text-text-heading mb-1">Welcome back</h2>
          <p class="text-[13px] text-text-muted mb-6">Sign in to your account</p>

          <form @submit.prevent="handleLogin" class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-text-body mb-1.5">Email</label>
              <input
                v-model="email"
                type="email"
                placeholder="you@example.com"
                required
                class="input w-full"
                autocomplete="email"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-text-body mb-1.5">Password</label>
              <input
                v-model="password"
                type="password"
                placeholder="Enter your password"
                required
                class="input w-full"
                autocomplete="current-password"
              />
            </div>

            <div v-if="error" class="text-[12px] text-red-500 font-medium bg-red-50 rounded-lg px-3 py-2">
              {{ error }}
            </div>

            <button
              type="submit"
              :disabled="loading || !email || !password"
              class="w-full py-2.5 bg-emerald-800 text-white rounded-lg text-[14px] font-semibold hover:bg-emerald-900 shadow-[0_1px_2px_rgba(6,78,59,0.4),0_1px_1px_rgba(6,78,59,0.2)] hover:shadow-[0_4px_14px_-2px_rgba(6,78,59,0.4),0_2px_6px_-1px_rgba(6,78,59,0.25)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none cursor-pointer"
            >
              {{ loading ? 'Signing in...' : 'Sign in' }}
            </button>
          </form>
        </div>

        <p class="text-center text-[11px] text-text-muted mt-6">
          LLM Knowledge Base &middot; Powered by AI
        </p>
      </div>
    </div>
  </div>
</template>
