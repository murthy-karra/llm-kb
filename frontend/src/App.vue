<script setup>
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { LayoutDashboard, BookOpen, FileText, MessageCircle, Search, LogOut } from 'lucide-vue-next'
import { useAuthStore } from './stores/auth'
import { useRouter } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLoginPage = computed(() => route.name === 'login')

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/wiki', label: 'Wiki', icon: BookOpen },
  { to: '/raw', label: 'Raw Sources', icon: FileText },
  { to: '/ask', label: 'Ask', icon: MessageCircle },
  { to: '/search', label: 'Search', icon: Search },
]

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <!-- Login page: no sidebar -->
  <RouterView v-if="isLoginPage" />

  <!-- App layout with sidebar -->
  <div v-else class="flex min-h-screen">
    <aside class="w-52 bg-card-bg border-r border-border flex flex-col shrink-0 shadow-[1px_0_3px_rgba(0,0,0,0.03)]">
      <div class="px-5 py-5">
        <h1 class="text-[15px] font-semibold text-text-heading tracking-tight">LLM KB</h1>
        <p class="text-[11px] text-text-muted mt-0.5 font-medium">Knowledge Base</p>
      </div>
      <nav class="flex-1 px-3 space-y-0.5">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2.5 px-3 py-[7px] rounded-lg text-[13px] font-medium text-text-body hover:text-text-heading hover:bg-surface-hover transition-all duration-200"
          active-class="!bg-accent-subtle !text-accent font-semibold"
        >
          <component :is="item.icon" :size="16" :stroke-width="2" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="px-3 pb-2">
        <button
          @click="handleLogout"
          class="flex items-center gap-2.5 w-full px-3 py-[7px] rounded-lg text-[13px] font-medium text-text-muted hover:text-red-600 hover:bg-red-50 transition-all duration-200 cursor-pointer"
        >
          <LogOut :size="16" :stroke-width="2" />
          Sign out
        </button>
      </div>
      <div class="px-5 py-3 border-t border-border">
        <div class="text-[12px] font-medium text-text-heading truncate">{{ auth.user?.name }}</div>
        <div class="text-[11px] text-text-muted truncate">{{ auth.user?.email }}</div>
      </div>
    </aside>

    <main class="flex-1 py-8 px-10 overflow-auto">
      <div class="max-w-3xl">
        <RouterView />
      </div>
    </main>
  </div>
</template>
