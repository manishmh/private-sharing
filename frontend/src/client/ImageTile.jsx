/*
 * One catalog page (presentational). The parent (CatalogViewer) drives loading
 * sequentially so every page loads even without scrolling. Each tile reserves
 * its real aspect ratio up front (no layout jump) and renders the image as a CSS
 * background — not <img src> — to make "save image" harder.
 *
 * `url`:  object URL when loaded, null while still loading, false on failure.
 */
export default function ImageTile({ url, width, height }) {
  const aspect = width && height ? `${width} / ${height}` : '3 / 4'

  return (
    <div className="tile" style={{ aspectRatio: aspect }}>
      {url ? (
        <div className="tile-img" style={{ backgroundImage: `url(${url})`, height: '100%' }}
             draggable={false} />
      ) : url === false ? (
        <div className="skeleton" style={{ height: '100%', display: 'grid', placeItems: 'center' }}>
          <span className="muted" style={{ fontSize: 13 }}>Couldn’t load this page</span>
        </div>
      ) : (
        <div className="skeleton" style={{ height: '100%' }} />
      )}
    </div>
  )
}
