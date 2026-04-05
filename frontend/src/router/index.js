import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import WikiListView from '../views/WikiListView.vue'
import WikiDetailView from '../views/WikiDetailView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', redirect: '/wikis' },
  { path: '/wikis', name: 'wikis', component: WikiListView },
  { path: '/wikis/:id', name: 'wiki-detail', component: WikiDetailView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('token')
  if (!token) {
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
