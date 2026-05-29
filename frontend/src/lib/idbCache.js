// IndexedDB caching via the `idb` library.
//  - `meta`   store: small key/value pairs (e.g. the device UUID).
//  - `images` store: per-(token,page) watermarked image Blobs for instant reloads.
import { openDB } from 'idb'

const DB_NAME = 'vault-cache'
const DB_VERSION = 1

const dbPromise = openDB(DB_NAME, DB_VERSION, {
  upgrade(db) {
    if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta')
    if (!db.objectStoreNames.contains('images')) db.createObjectStore('images')
  },
})

// ---- generic key/value (meta) ----
export async function kvGet(key) {
  return (await dbPromise).get('meta', key)
}
export async function kvSet(key, val) {
  return (await dbPromise).put('meta', val, key)
}

// ---- image blob cache ----
const imgKey = (token, page) => `${token}:${page}`

export async function getCachedImage(token, page) {
  return (await dbPromise).get('images', imgKey(token, page))
}
export async function putCachedImage(token, page, blob) {
  return (await dbPromise).put('images', blob, imgKey(token, page))
}
export async function hasCachedImage(token, page) {
  const v = await (await dbPromise).getKey('images', imgKey(token, page))
  return v !== undefined
}

// Remove every cached image for a single link (keys are "<token>:<page>").
// Used when a link is no longer active so confidential pages don't linger locally.
// The shared device UUID in `meta` is intentionally left intact.
export async function clearTokenImages(token) {
  const db = await dbPromise
  const tx = db.transaction('images', 'readwrite')
  const prefix = `${token}:`
  let cursor = await tx.store.openCursor()
  while (cursor) {
    if (typeof cursor.key === 'string' && cursor.key.startsWith(prefix)) {
      await cursor.delete()
    }
    cursor = await cursor.continue()
  }
  await tx.done
}
