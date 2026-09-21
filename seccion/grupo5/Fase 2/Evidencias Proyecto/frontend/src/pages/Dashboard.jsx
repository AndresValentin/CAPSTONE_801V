import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Database, LogOut } from 'lucide-react'
import Sidebar from '../components/Sidebar.jsx'
import FiltersPanel from '../components/FiltersPanel.jsx'
import DashboardPanel from '../components/DashboardPanel.jsx'
import ChatCopilot from '../components/ChatCopilot.jsx'
import { filtrarSiniestros, siniestrosBase } from '../data/mockData.js'
import './Dashboard.css'

const filtrosIniciales = {
  producto: 'Todos',
  region: 'Todas',
  estado: 'Todos',
  desde: '',
  hasta: '',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [filtros, setFiltros] = useState(filtrosIniciales)
  const [dataset, setDataset] = useState(siniestrosBase)
  const [historial, setHistorial] = useState([])
  const [ultimaSolicitud, setUltimaSolicitud] = useState(null)

  const datosFiltrados = useMemo(() => filtrarSiniestros(dataset, filtros), [dataset, filtros])

  function aplicarFiltrosDesdeChat(nuevosFiltros) {
    setFiltros((prev) => ({ ...prev, ...nuevosFiltros }))
  }

  function registrarSolicitud(registro) {
    setHistorial((prev) => [...prev, registro])
    setUltimaSolicitud(registro)
  }

  function seleccionarReporte(registro) {
    if (registro.interpretacion?.filtros) {
      aplicarFiltrosDesdeChat({
        producto: registro.interpretacion.filtros.producto || 'Todos',
        region: registro.interpretacion.filtros.region || 'Todas',
        estado: registro.interpretacion.filtros.estado || 'Todos',
      })
    }
    setUltimaSolicitud(registro)
  }

  function importarRegistros(nuevos) {
    setDataset((prev) => [...prev, ...nuevos])
  }

  return (
    <div className="dashboard-screen">
      <header className="dashboard-header">
        <div className="brand">
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
          <span className="brand-name">BI Copilot</span>
        </div>
        <div className="header-meta">
          <span className="domain-pill"><Database size={13} /> Dominio: Siniestros ({dataset.length} registros)</span>
          <button className="btn-logout" onClick={() => navigate('/')}>
            <LogOut size={14} /> Cerrar sesión
          </button>
        </div>
      </header>

      <main className="dashboard-grid">
        <Sidebar
          historial={historial}
          onSeleccionarReporte={seleccionarReporte}
          onImportar={importarRegistros}
          datos={datosFiltrados}
        />

        <div className="main-column">
          <FiltersPanel filtros={filtros} setFiltros={setFiltros} resultados={datosFiltrados.length} />
          <DashboardPanel datos={datosFiltrados} filtros={filtros} solicitud={ultimaSolicitud} />
        </div>

        <ChatCopilot onFiltrosSugeridos={aplicarFiltrosDesdeChat} onNuevaSolicitud={registrarSolicitud} />
      </main>
    </div>
  )
}
