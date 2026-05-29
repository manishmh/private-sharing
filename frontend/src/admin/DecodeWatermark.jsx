import { useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../api'

export default function DecodeWatermark() {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setErr(''); setResult(null); setBusy(true)
    try { setResult(await adminApi.decodeWatermark(file)) }
    catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  return (
    <div className="stack" style={{ maxWidth: 560 }}>
      <Link to="/admin" className="muted" style={{ fontSize: 13 }}>← Catalogs</Link>
      <h2 style={{ margin: 0 }}>Decode forensic watermark</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Upload a leaked image file. If it still contains the invisible LSB payload, it will be
        decoded back to the exact client and link.
      </p>
      <form className="card stack" onSubmit={submit}>
        <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <div><button className="primary" disabled={busy || !file}>{busy ? 'Decoding…' : 'Decode'}</button></div>
      </form>

      {err && <div className="card pill danger">{err}</div>}
      {result && (
        <div className="card stack">
          {result.found ? (
            <>
              <span className="pill ok">Watermark found</span>
              <table>
                <tbody>
                  <tr><th>Token</th><td className="mono">{result.token}</td></tr>
                  <tr><th>Client</th><td>{result.client_label}</td></tr>
                  <tr><th>Embedded at</th><td>{result.timestamp ? new Date(result.timestamp * 1000).toLocaleString() : '—'}</td></tr>
                  <tr><th>Raw payload</th><td className="mono" style={{ fontSize: 12 }}>{result.payload}</td></tr>
                </tbody>
              </table>
            </>
          ) : (
            <span className="pill warn">No decodable watermark (image may have been recompressed or is not from Vault).</span>
          )}
        </div>
      )}
    </div>
  )
}
