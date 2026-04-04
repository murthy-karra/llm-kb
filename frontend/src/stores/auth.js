import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  let refreshTimer = null

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(t, u) {
    token.value = t
    user.value = u
    localStorage.setItem('token', t)
    localStorage.setItem('user', JSON.stringify(u))
    scheduleRefresh()
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
  }

  // Refresh access token 1 minute before it expires (at ~14 min)
  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      refresh()
    }, 14 * 60 * 1000)
  }

  async function login(email, password) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    setAuth(data.token, data.user)
    return data
  }

  async function refresh() {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      })
      if (!res.ok) {
        clearAuth()
        window.location.href = '/login'
        return
      }
      const data = await res.json()
      setAuth(data.token, data.user)
    } catch {
      clearAuth()
      window.location.href = '/login'
    }
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    clearAuth()
  }

  async function checkAuth() {
    if (!token.value) return false
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (!res.ok) {
        // Access token expired — try refresh
        const refreshRes = await fetch('/api/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        })
        if (!refreshRes.ok) {
          clearAuth()
          return false
        }
        const data = await refreshRes.json()
        setAuth(data.token, data.user)
        return true
      }
      user.value = await res.json()
      scheduleRefresh()
      return true
    } catch {
      clearAuth()
      return false
    }
  }

  // Start refresh timer if we already have a token
  if (token.value) scheduleRefresh()

  return { token, user, isAuthenticated, login, logout, checkAuth, refresh }
})
