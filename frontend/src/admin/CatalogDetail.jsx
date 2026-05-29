import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { adminApi } from '../api'

function CreateLinkForm({ catalogId, onCreated }) {
  const [label, setLabel] = useState('')
  const [maxDevices, setMaxDevices] = useState(1)
  const [expires, setExpires] = useState('') // datetime-local string; empty = never
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      const body = {
        client_label: label,
        max_devices: Number(maxDevices),
        expires_at: expires ? new Date(expires).toISOString() : null,
      }
      const link = await adminApi.createLink(catalogId, body)
      setLabel(''); setMaxDevices(1); setExpires('')
      onCreated(link)
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <strong>Create a share link</strong>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div className="field" style={{ flex: '2 1 200px', marginBottom: 0 }}>
          <label>Client label</label>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Rajesh Textiles" />
        </div>
        <div className="field" style={{ flex: '1 1 110px', marginBottom: 0 }}>
          <label>Max devices</label>
          <input type="number" min="1" value={maxDevices} onChange={(e) => setMaxDevices(e.target.value)} />
        </div>
        <div className="field" style={{ flex: '2 1 200px', marginBottom: 0 }}>
          <label>Expires (blank = never)</label>
          <input type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} />
        </div>
      </div>
      {err && <div className="pill danger">{err}</div>}
      <div><button className="primary" disabled={busy || !label}>{busy ? 'Creating…' : 'Mint link'}</button></div>
    </form>
  )
}

function CopyIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

function LinkRow({ link, onChange, onDelete }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)
  const [devCount, setDevCount] = useState(link.max_devices)
  const [limitMsg, setLimitMsg] = useState('')
  const fullUrl = `${window.location.origin}${link.public_url}`

  // Keep the device input in sync if the link's limit changes elsewhere.
  useEffect(() => { setDevCount(link.max_devices) }, [link.max_devices])

  const patch = async (body) => {
    setErr(''); setBusy(true)
    try { onChange(await adminApi.updateLink(link.token, body)); return true }
    catch (e) { setErr(e.message); return false } finally { setBusy(false) }
  }

  const updateDevices = async () => {
    const n = Number(devCount)
    if (!Number.isInteger(n) || n < 1) { setErr('Enter a whole number ≥ 1'); return }
    if (n === link.max_devices) { setLimitMsg(`Already set to ${n}`); setTimeout(() => setLimitMsg(''), 1800); return }
    if (await patch({ max_devices: n })) {
      setLimitMsg(`Limit set to ${n}`)
      setTimeout(() => setLimitMsg(''), 1800)
    }
  }
  const toggleRevoke = () => patch({ revoked: !link.revoked })
  const removeLink = async () => {
    const msg = link.revoked
      ? `Delete link "${link.client_label}" (${link.token})?\n\nThis permanently removes the link and its devices/analytics. This cannot be undone.`
      : `Delete link "${link.client_label}" (${link.token})?\n\nThis link is ACTIVE — it will be revoked and deleted immediately, cutting off access for its devices. This cannot be undone.`
    if (!window.confirm(msg)) return
    setErr(''); setBusy(true)
    try { await adminApi.deleteLink(link.token); onDelete(link.token) }
    catch (e) { setErr(e.message); setBusy(false) }
  }
  const setExpiry = () => {
    const v = prompt('Expire at (YYYY-MM-DD HH:MM, local). Leave blank to cancel:')
    if (v === null || v.trim() === '') return
    const d = new Date(v.replace(' ', 'T'))
    if (isNaN(d)) { setErr('Invalid date'); return }
    patch({ expires_at: d.toISOString() })
  }
  const clearExpiry = () => patch({ clear_expiry: true })
  const copy = async () => {
    try { await navigator.clipboard?.writeText(fullUrl) } catch {}
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  const status = link.revoked
    ? <span className="pill danger">revoked</span>
    : (link.expires_at && new Date(link.expires_at) < new Date())
      ? <span className="pill warn">expired</span>
      : <span className="pill ok">active</span>

  return (
    <tr>
      <td>
        <div><strong>{link.client_label}</strong></div>
        <div className="mono muted" style={{ fontSize: 12 }}>{link.token}</div>
        <button className={`copy-btn${copied ? ' copied' : ''}`} onClick={copy}>
          <CopyIcon /> {copied ? 'Link copied!' : 'Copy link'}
        </button>
        {err && <div className="pill danger" style={{ marginTop: 6 }}>{err}</div>}
      </td>
      <td>
        <div style={{ marginBottom: 6 }}>
          <strong>{link.registered_count}</strong> / {link.max_devices} used
        </div>
        <div className="row" style={{ gap: 6 }}>
          <input type="number" min="1" value={devCount}
                 onChange={(e) => setDevCount(e.target.value)}
                 style={{ width: 64, padding: '8px 10px' }} aria-label="Max devices" />
          <button className="primary" disabled={busy} onClick={updateDevices}>Set limit</button>
        </div>
        {limitMsg && <div className="pill ok" style={{ marginTop: 6 }}>{limitMsg}</div>}
      </td>
      <td style={{ fontSize: 13 }}>
        {link.expires_at ? new Date(link.expires_at).toLocaleString() : <span className="muted">never</span>}
        <div className="row" style={{ gap: 6, marginTop: 6 }}>
          <button className="ghost" style={{ fontSize: 12, padding: '4px 10px' }} disabled={busy} onClick={setExpiry}>Set</button>
          {link.expires_at && (
            <button className="ghost" style={{ fontSize: 12, padding: '4px 10px' }} disabled={busy} onClick={clearExpiry}>Clear</button>
          )}
        </div>
      </td>
      <td>{status}</td>
      <td>
        <div className="stack" style={{ gap: 6 }}>
          <Link to={`/admin/link/${link.token}/analytics`}>
            <button className="ghost" style={{ fontSize: 12, padding: '6px 10px', width: '100%' }}>Analytics</button>
          </Link>
          <button className={link.revoked ? 'ghost' : 'danger'} style={{ fontSize: 12, padding: '6px 10px' }}
                  disabled={busy} onClick={toggleRevoke}>
            {link.revoked ? 'Un-revoke' : 'Revoke'}
          </button>
          <button className="ghost" style={{ fontSize: 12, padding: '6px 10px', color: 'var(--danger)' }}
                  disabled={busy} onClick={removeLink}>Delete</button>
        </div>
      </td>
    </tr>
  )
}

export default function CatalogDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [catalog, setCatalog] = useState(null)
  const [err, setErr] = useState('')
  const [deleting, setDeleting] = useState(false)

  const load = () => adminApi.getCatalog(id).then(setCatalog).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [id])

  const replaceLink = (updated) =>
    setCatalog((c) => ({ ...c, links: c.links.map((l) => (l.token === updated.token ? updated : l)) }))
  const addLink = (link) => setCatalog((c) => ({ ...c, links: [link, ...c.links] }))
  const removeLink = (token) =>
    setCatalog((c) => ({ ...c, links: c.links.filter((l) => l.token !== token) }))

  const remove = async () => {
    const n = catalog.links.length
    const msg = `Delete "${catalog.title}"?\n\nThis permanently removes the catalog, its ${catalog.page_count} page image(s)` +
      (n ? ` and all ${n} share link(s)` : '') + '. This cannot be undone.'
    if (!window.confirm(msg)) return
    setDeleting(true)
    try {
      await adminApi.deleteCatalog(catalog.id)
      navigate('/admin')
    } catch (e) {
      setErr(e.message)
      setDeleting(false)
    }
  }

  if (err) return <div className="card pill danger">{err}</div>
  if (!catalog) return <div className="muted">Loading…</div>

  return (
    <div className="stack">
      <Link to="/admin" className="muted" style={{ fontSize: 13 }}>← All catalogs</Link>
      <div className="spread">
        <div>
          <h2 style={{ margin: 0 }}>{catalog.title}</h2>
          <div className="muted mono" style={{ fontSize: 13 }}>{catalog.slug} · {catalog.page_count} pages</div>
        </div>
        <button className="danger" disabled={deleting} onClick={remove}>
          {deleting ? 'Deleting…' : 'Delete catalog'}
        </button>
      </div>

      <CreateLinkForm catalogId={catalog.id} onCreated={addLink} />

      <div className="card">
        <strong>Share links ({catalog.links.length})</strong>
        {catalog.links.length === 0 ? (
          <p className="muted">No links yet — mint one above.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr><th>Client / token</th><th>Devices</th><th>Expires</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {catalog.links.map((l) => (
                  <LinkRow key={l.token} link={l} onChange={replaceLink} onDelete={removeLink} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
