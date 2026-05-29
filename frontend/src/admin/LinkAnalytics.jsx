import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { adminApi } from '../api'

function Stat({ label, value, tone }) {
  return (
    <div className="card" style={{ flex: '1 1 120px', textAlign: 'center' }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: tone }}>{value}</div>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
    </div>
  )
}

export default function LinkAnalytics() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    adminApi.analytics(token).then(setData).catch((e) => setErr(e.message))
  }, [token])

  if (err) return <div className="card pill danger">{err}</div>
  if (!data) return <div className="muted">Loading…</div>

  return (
    <div className="stack">
      <Link to={`/admin`} className="muted" style={{ fontSize: 13 }}>← Catalogs</Link>
      <div className="spread">
        <div>
          <h2 style={{ margin: 0 }}>{data.client_label}</h2>
          <div className="muted mono" style={{ fontSize: 13 }}>
            {token} · {data.registered_count}/{data.max_devices} devices ·{' '}
            {data.revoked ? 'revoked' : data.expires_at ? `expires ${new Date(data.expires_at).toLocaleString()}` : 'never expires'}
          </div>
        </div>
      </div>

      <div className="row">
        <Stat label="Total opens" value={data.total_opens} tone="var(--ok)" />
        <Stat label="Registered devices" value={data.registered_count} tone="var(--accent)" />
        <Stat label="Blocked attempts" value={data.blocked_attempts} tone="var(--warn)" />
        <Stat label="Revoked attempts" value={data.revoked_attempts} tone="var(--danger)" />
      </div>

      <div className="card">
        <strong>Devices</strong>
        {data.devices.length === 0 ? (
          <p className="muted">No devices have opened this link yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr><th>Device</th><th>Approx location</th><th>Opens</th><th>First seen</th><th>Last seen</th></tr>
              </thead>
              <tbody>
                {data.devices.map((d, i) => (
                  <tr key={i}>
                    <td><strong>{d.friendly_name}</strong></td>
                    <td>{d.approx_location}</td>
                    <td>{d.open_count}</td>
                    <td style={{ fontSize: 13 }}>{new Date(d.first_seen).toLocaleString()}</td>
                    <td style={{ fontSize: 13 }}>{new Date(d.last_seen).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          Raw fingerprint, full user-agent and IP are recorded on the backend only and are
          intentionally not shown here.
        </p>
      </div>
    </div>
  )
}
