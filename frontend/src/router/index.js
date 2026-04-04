import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import Dashboard from '../views/Dashboard.vue'
import WikiBrowser from '../views/WikiBrowser.vue'
import ArticleView from '../views/ArticleView.vue'
import RawFiles from '../views/RawFiles.vue'
import AskView from '../views/AskView.vue'
import SearchView from '../views/SearchView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', name: 'dashboard', component: Dashboard },
  { path: '/wiki', name: 'wiki', component: WikiBrowser },
  { path: '/wiki/:path(.*)', name: 'article', component: ArticleView },
  { path: '/raw', name: 'raw', component: RawFiles },
  { path: '/ask', name: 'ask', component: AskView },
  { path: '/search', name: 'search', component: SearchView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('token')
  if (!token) {
    // No access token — try silent refresh via httpOnly cookie
    try {
      const res = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
      if (res.ok) {
        const data = await res.json()
        localStorage.setItem('token', data.token)
        localStorage.setItem('user', JSON.stringify(data.user))
        return true
      }
    } catch {}
    return { name: 'login' }
  }
  return true
})

export default router
