import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { publicApi } from '../api'
import { getDeviceIdentity } from '../lib/device'
import { clearTokenImages, getCachedImage, putCachedImage } from '../lib/idbCache'
import { installDeterrents, installVisibilityGuard } from '../lib/deterrents'
import ImageTile from './ImageTile'
import StatusScreen from './StatusScreen'

// Token is the 6 chars after the final '-' in the URL segment (slug-Ab3xK9).
function parseToken(linkId) {
  if (!linkId) return ''
  const idx = linkId.lastIndexOf('-')
  return idx === -1 ? linkId : linkId.slice(idx + 1)
}

export default function CatalogViewer() {
  const { linkId } = useParams()
  const token = parseToken(linkId)

  const [phase, setPhase] = useState('loading') // loading|ready|blocked|expired|revoked|notfound|error
  const [manifest, setManifest] = useState(null)
  const [deviceId, setDeviceId] = useState(null)
  const [hidden, setHidden] = useState(false)
  const [urls, setUrls] = useState({})   // page_index -> objectURL | false(failed)
  const [loaded, setLoaded] = useState(0)
  const startedRef = useRef(false)

  // Screenshot deterrents + privacy overlay on focus loss (best-effort; see deterrents.js).
  useEffect(() => {
    const u1 = installDeterrents()
    const u2 = installVisibilityGuard(setHidden)
    return () => { u1(); u2() }
  }, [])

  useEffect(() => {
    if (startedRef.current) return // guard against StrictMode double-run
    startedRef.current = true

    ;(async () => {
      try {
        const { deviceId, fingerprint } = await getDeviceIdentity()
        setDeviceId(deviceId)

        // resolve() sets the httpOnly identity cookie; access() makes the decision.
        const meta = await publicApi.resolve(token)
        if (meta.status === 'not_found') { setPhase('notfound'); return }

        const decision = await publicApi.access(token, deviceId, fingerprint)
        if (decision.status === 'allowed') {
          const m = await publicApi.manifest(token, deviceId)
          setManifest(m)
          setPhase('ready')
        } else if (decision.status === 'expired') {
          // Link no longer active: purge this link's cached pages from IndexedDB.
          await clearTokenImages(token)
          setPhase('expired')
        } else if (decision.status === 'revoked') {
          await clearTokenImages(token)
          setPhase('revoked')
        } else {
          setPhase('blocked')
        }
      } catch {
        setPhase('error')
      }
    })()
  }, [token])

  // While the catalog is open, poll the link status every 30s so a revoke or
  // expiry takes effect without the client manually refreshing. resolve() only
  // reports status (no access decision/logging). On revoke/expiry, purge cache.
  useEffect(() => {
    if (phase !== 'ready') return
    let stop = false
    const id = setInterval(async () => {
      try {
        const meta = await publicApi.resolve(token)
        if (stop) return
        if (meta.status === 'revoked') { await clearTokenImages(token); setPhase('revoked') }
        else if (meta.status === 'expired') { await clearTokenImages(token); setPhase('expired') }
        else if (meta.status === 'not_found') { setPhase('notfound') }
      } catch {
        // Transient network/backend error — keep showing the catalog, retry next tick.
      }
    }, 30000)
    return () => { stop = true; clearInterval(id) }
  }, [phase, token])

  // Sequentially load EVERY page (page 0 first), even without scrolling.
  // Cache-first: served from IndexedDB instantly on a return visit, otherwise
  // fetched once and stored. The in-order loop naturally prioritizes the first
  // (visible) images, then fills in the rest one by one.
  useEffect(() => {
    if (!manifest || !deviceId) return
    let cancelled = false
    const created = []

    ;(async () => {
      for (const p of manifest.pages) {
        if (cancelled) break
        try {
          let blob = await getCachedImage(token, p.page_index)
          if (!blob) {
            blob = await publicApi.pageBlob(token, p.page_index, deviceId)
            await putCachedImage(token, p.page_index, blob)
          }
          if (cancelled) break
          const u = URL.createObjectURL(blob)
          created.push(u)
          setUrls((prev) => ({ ...prev, [p.page_index]: u }))
        } catch {
          if (!cancelled) setUrls((prev) => ({ ...prev, [p.page_index]: false }))
        } finally {
          if (!cancelled) setLoaded((n) => n + 1)
        }
      }
    })()

    return () => {
      cancelled = true
      created.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [manifest, deviceId, token])

  if (phase === 'loading') {
    return (
      <div className="center-spin">
        <div className="spinner" />
        <div className="muted">Loading catalog…</div>
      </div>
    )
  }
  if (phase !== 'ready') return <StatusScreen kind={phase} />

  return (
    <div className="viewer no-capture">
      <div className="capture-flash" id="vault-capture-flash" />
      {hidden && (
        <div className="privacy-overlay" style={{ opacity: 1 }}>
          <div>
            <div style={{ fontSize: 32, marginBottom: 10 }}>🔒</div>
            Content hidden while the app is in the background.
          </div>
        </div>
      )}

      <div className="viewer-head">
        <div className="viewer-title">{manifest.title}</div>
        <div className="muted" style={{ fontSize: 12 }}>
          {manifest.page_count} designs · confidential · watermarked to you
          {loaded < manifest.page_count && ` · loading ${loaded}/${manifest.page_count}`}
        </div>
      </div>

      <div className="feed">
        {manifest.pages.map((p) => (
          <ImageTile
            key={p.page_index}
            url={urls[p.page_index] ?? null}
            width={p.width}
            height={p.height}
          />
        ))}
      </div>
    </div>
  )
}
