// Stable device identity = FingerprintJS visitorId + a self-generated UUID
// persisted in IndexedDB. The backend additionally folds in an httpOnly cookie,
// so clearing any single source does not trivially reset the device identity.
import FingerprintJS from '@fingerprintjs/fingerprintjs'
import { kvGet, kvSet } from './idbCache'

const UUID_KEY = 'vault_device_uuid'

function genUuid() {
  if (crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

async function getOrCreateUuid() {
  let u = await kvGet(UUID_KEY)
  // Fall back to a localStorage mirror so a cleared IndexedDB alone doesn't reset us.
  if (!u) {
    try { u = localStorage.getItem(UUID_KEY) || null } catch { u = null }
  }
  if (!u) {
    u = genUuid()
    await kvSet(UUID_KEY, u)
  } else {
    await kvSet(UUID_KEY, u)
  }
  try { localStorage.setItem(UUID_KEY, u) } catch {}
  return u
}

async function sha256Hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str))
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

let _cached = null

// Returns { deviceId, fingerprint }. deviceId is a per-browser stable hash; the
// backend folds in its httpOnly cookie to finalize the per-browser identity.
export async function getDeviceIdentity() {
  if (_cached) return _cached
  const uuid = await getOrCreateUuid()
  let visitorId = 'no-fp'
  try {
    const fp = await FingerprintJS.load()
    const res = await fp.get()
    visitorId = res.visitorId
  } catch {
    // Fingerprinting can fail in locked-down browsers; UUID still anchors identity.
  }
  const deviceId = (await sha256Hex(`${visitorId}:${uuid}`)).slice(0, 40)
  _cached = { deviceId, fingerprint: visitorId }
  return _cached
}
