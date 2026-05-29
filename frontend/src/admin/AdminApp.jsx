import { Link, Route, Routes } from 'react-router-dom'
import CatalogList from './CatalogList'
import UploadCatalog from './UploadCatalog'
import CatalogDetail from './CatalogDetail'
import LinkAnalytics from './LinkAnalytics'
import DecodeWatermark from './DecodeWatermark'

// Admin auth is disabled — the console is shown directly on load.
export default function AdminApp() {
  return (
    <div className="admin-shell">
      <div className="admin-head">
        <Link to="/admin" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="brand">VAULT<small>secure design catalog console</small></div>
        </Link>
        <div className="row">
          <Link to="/admin/decode"><button className="ghost">Decode watermark</button></Link>
        </div>
      </div>

      <Routes>
        <Route index element={<CatalogList />} />
        <Route path="upload" element={<UploadCatalog />} />
        <Route path="catalog/:id" element={<CatalogDetail />} />
        <Route path="link/:token/analytics" element={<LinkAnalytics />} />
        <Route path="decode" element={<DecodeWatermark />} />
      </Routes>
    </div>
  )
}
