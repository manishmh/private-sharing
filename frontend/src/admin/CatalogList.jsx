import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../api'

export default function CatalogList() {
  const [catalogs, setCatalogs] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    adminApi.listCatalogs().then(setCatalogs).catch((e) => setErr(e.message))
  }, [])

  return (
    <div className="stack">
      <div className="spread">
        <h2 style={{ margin: 0 }}>Catalogs</h2>
        <Link to="/admin/upload"><button className="primary">+ Upload PDF</button></Link>
      </div>

      {err && <div className="card pill danger">{err}</div>}
      {catalogs === null && <div className="muted">Loading…</div>}
      {catalogs && catalogs.length === 0 && (
        <div className="card muted">No catalogs yet. Upload a PDF to create your first one.</div>
      )}

      <div className="grid">
        {catalogs?.map((c) => (
          <Link key={c.id} to={`/admin/catalog/${c.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="card stack" style={{ height: '100%' }}>
              <div className="spread">
                <strong>{c.title}</strong>
                <span className="pill">{c.page_count} pages</span>
              </div>
              <div className="muted mono" style={{ fontSize: 13 }}>{c.slug}</div>
              <div className="spread">
                <span className="muted" style={{ fontSize: 13 }}>{c.link_count} link(s)</span>
                <span className="muted" style={{ fontSize: 12 }}>
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
