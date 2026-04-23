const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function getToken() {
  return localStorage.getItem('dropoff_access_token')
}

async function request(path, options = {}, withAuth = false) {
  const headers = new Headers(options.headers || {})

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (withAuth) {
    const token = getToken()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return null
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload?.detail ? payload.detail : 'Request failed'
    throw new Error(detail)
  }

  return payload
}

export function apiGet(path, withAuth = false) {
  return request(path, { method: 'GET' }, withAuth)
}

export function apiPost(path, body, withAuth = false) {
  return request(path, { method: 'POST', body: JSON.stringify(body) }, withAuth)
}

export function apiPatch(path, body, withAuth = false) {
  return request(path, { method: 'PATCH', body: JSON.stringify(body) }, withAuth)
}

export function apiDelete(path, withAuth = false) {
  return request(path, { method: 'DELETE' }, withAuth)
}

export function apiUpload(path, file, withAuth = false) {
  const formData = new FormData()
  formData.append('file', file)
  return request(path, { method: 'POST', body: formData }, withAuth)
}