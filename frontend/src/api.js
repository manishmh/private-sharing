// Thin fetch wrapper. In dev, Vite proxies /api to the backend (admin API lives
// under /api/admin, public under /api/v; the /admin and /v UI routes are SPA).
// `credentials: 'include'` ensures the httpOnly identity cookie round-trips.
// NOTE: admin auth is currently disabled (open console), so no password header.

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch {}
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res
}

// ---- Admin API ----
export const adminApi = {
  uploadCatalog: (title, file) => {
    const fd = new FormData()
    fd.append('title', title)
    fd.append('file', file)
    return fetch('/api/admin/catalogs', { method: 'POST', body: fd }).then(handle)
  },

  listCatalogs: () => fetch('/api/admin/catalogs').then(handle),

  getCatalog: (id) => fetch(`/api/admin/catalogs/${id}`).then(handle),

  deleteCatalog: (id) => fetch(`/api/admin/catalogs/${id}`, { method: 'DELETE' }).then(handle),

  createLink: (catalogId, body) =>
    fetch(`/api/admin/catalogs/${catalogId}/links`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(handle),

  updateLink: (token, body) =>
    fetch(`/api/admin/links/${token}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(handle),

  deleteLink: (token) => fetch(`/api/admin/links/${token}`, { method: 'DELETE' }).then(handle),

  analytics: (token) => fetch(`/api/admin/links/${token}/analytics`).then(handle),

  decodeWatermark: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch('/api/admin/decode-watermark', { method: 'POST', body: fd }).then(handle)
  },
}

// ---- Public client API ----
export const publicApi = {
  resolve: (token) =>
    fetch(`/api/v/${token}`, { credentials: 'include' }).then(handle),

  access: (token, deviceId, fingerprint) =>
    fetch(`/api/v/${token}/access`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, fingerprint_hash: fingerprint }),
    }).then(handle),

  manifest: (token, deviceId) =>
    fetch(`/api/v/${token}/manifest`, {
      credentials: 'include',
      headers: { 'X-Device-Id': deviceId },
    }).then(handle),

  // Returns a Blob for IndexedDB caching.
  pageBlob: (token, page, deviceId) =>
    fetch(`/api/v/${token}/page/${page}.webp`, {
      credentials: 'include',
      headers: { 'X-Device-Id': deviceId },
    }).then((res) => {
      if (!res.ok) throw Object.assign(new Error('image fetch failed'), { status: res.status })
      return res.blob()
    }),
}
