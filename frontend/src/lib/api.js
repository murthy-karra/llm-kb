/**
 * Authenticated fetch wrapper with automatic token refresh on 401.
 *
 * Usage: import { apiFetch } from '@/lib/api'
 *        const res = await apiFetch('/api/wikis')
 *        const data = await res.json()
 */

let refreshPromise = null

async function refreshToken() {
  const res = await fetch('/api/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  const data = await res.json()
  localStorage.setItem('token', data.token)
  localStorage.setItem('user', JSON.stringify(data.user))
  return data.token
}

export async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('token')

  const headers = { ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  let res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    // Deduplicate concurrent refresh attempts
    if (!refreshPromise) {
      refreshPromise = refreshToken().finally(() => {
        refreshPromise = null
      })
    }

    const newToken = await refreshPromise

    headers['Authorization'] = `Bearer ${newToken}`
    res = await fetch(url, { ...options, headers })
  }

  return res
}
