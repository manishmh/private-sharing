import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminApi } from '../api'

export default function UploadCatalog() {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    if (!file || !title) return
    setErr('')
    setBusy(true)
    try {
      const catalog = await adminApi.uploadCatalog(title, file)
      navigate(`/admin/catalog/${catalog.id}`)
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack" style={{ maxWidth: 520 }}>
      <h2 style={{ margin: 0 }}>Upload a PDF</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        The PDF is processed once: each page becomes a clean master image. After this you can
        mint unlimited share links without re-uploading.
      </p>
      <form className="card stack" onSubmit={submit}>
        <div className="field">
          <label>Catalog title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)}
                 placeholder="Silk Aura Vol 6" autoFocus />
        </div>
        <div className="field">
          <label>PDF file</label>
          <input type="file" accept="application/pdf"
                 onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        {err && <div className="pill danger">{err}</div>}
        <div className="row">
          <button className="primary" disabled={busy || !file || !title}>
            {busy ? 'Processing PDF…' : 'Create catalog'}
          </button>
          <button type="button" className="ghost" onClick={() => navigate('/admin')}>Cancel</button>
        </div>
      </form>
    </div>
  )
}
