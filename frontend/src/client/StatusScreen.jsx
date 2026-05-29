// Friendly full-screen states for blocked / expired / revoked / not-found / error.

const PRESETS = {
  blocked: {
    icon: '🔒',
    title: 'Device limit reached',
    body: 'This link has already been opened on the maximum number of devices. Please contact your sales rep to have your device added.',
  },
  expired: {
    icon: '⌛',
    title: 'This link is no longer active',
    body: 'The share link has expired. Please contact your sales rep for an updated link.',
  },
  revoked: {
    icon: '⛔',
    title: 'This link is no longer active',
    body: 'Access to this catalog has been withdrawn. Please contact your sales rep.',
  },
  notfound: {
    icon: '🔎',
    title: 'Catalog not found',
    body: 'This link doesn’t point to a valid catalog. Please check the link and try again.',
  },
  error: {
    icon: '⚠️',
    title: 'Something went wrong',
    body: 'We couldn’t load this catalog right now. Please try again in a moment.',
  },
}

export default function StatusScreen({ kind }) {
  const p = PRESETS[kind] || PRESETS.error
  return (
    <div className="status-screen">
      <div className="card status-card">
        <div className="status-icon">{p.icon}</div>
        <h1>{p.title}</h1>
        <p className="muted">{p.body}</p>
      </div>
    </div>
  )
}
