import ReportsLog from './ReportsLog.jsx'
import ImportExcel from './ImportExcel.jsx'
import MLPanel from './MLPanel.jsx'
import './Sidebar.css'

export default function Sidebar({ historial, onSeleccionarReporte, onImportar, datos }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-module">
        <ReportsLog historial={historial} onSeleccionar={onSeleccionarReporte} />
      </div>
      <div className="sidebar-module">
        <ImportExcel onImportar={onImportar} />
      </div>
      <div className="sidebar-module">
        <MLPanel datos={datos} />
      </div>
    </aside>
  )
}
