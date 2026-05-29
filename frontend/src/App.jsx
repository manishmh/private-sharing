import { Navigate, Route, Routes } from 'react-router-dom'
import AdminApp from './admin/AdminApp'
import CatalogViewer from './client/CatalogViewer'

export default function App() {
  return (
    <Routes>
      {/* Client viewer: /v/{slug}-{token} */}
      <Route path="/v/:linkId" element={<CatalogViewer />} />
      {/* Admin console */}
      <Route path="/admin/*" element={<AdminApp />} />
      <Route path="/" element={<Navigate to="/admin" replace />} />
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  )
}
