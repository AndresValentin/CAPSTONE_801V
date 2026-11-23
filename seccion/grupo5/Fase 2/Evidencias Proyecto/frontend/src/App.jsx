import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Biblioteca from './pages/Biblioteca.jsx'
import VistaDashboard from './pages/VistaDashboard.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/dashboards" element={<Biblioteca />} />
      <Route path="/dashboards/:id" element={<VistaDashboard />} />
      <Route path="/recuperar" element={<Login recuperar />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
