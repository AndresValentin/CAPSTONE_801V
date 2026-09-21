import { History, CheckCircle2, XCircle } from 'lucide-react'
import './ReportsLog.css'

function formatearHora(fecha) {
  return fecha.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
}

function resumenFiltros(filtros = {}) {
  return Object.entries(filtros)
    .filter(([, v]) => v && v !== 'Todos' && v !== 'Todas')
    .map(([, v]) => v)
    .join(' · ')
}

export default function ReportsLog({ historial, onSeleccionar }) {
  const items = [...historial].reverse()

  return (
    <div className="reports-module">
      <div className="module-title">
        <span className="module-title-icon"><History size={13} /></span>
        Registro de reportes
      </div>
      <p className="module-hint">Chats con IA y su dashboard resultante (RF-08)</p>

      {items.length === 0 && <p className="reports-empty">Aún no hay solicitudes registradas.</p>}

      <ul className="reports-list">
        {items.map((item) => {
          const filtrosTexto = item.interpretacion ? resumenFiltros(item.interpretacion.filtros) : ''
          return (
            <li
              key={item.id}
              className={`report-item ${item.estado === 'validado' ? 'clickable' : ''}`}
              onClick={() => item.estado === 'validado' && onSeleccionar?.(item)}
            >
              <div className="report-item-head">
                {item.estado === 'validado'
                  ? <CheckCircle2 size={13} className="icon-ok" />
                  : <XCircle size={13} className="icon-fail" />}
                <span className="report-time">{formatearHora(item.fecha)}</span>
              </div>
              <p className="report-text">{item.texto}</p>
              {item.estado === 'validado' ? (
                <div className="report-dashboard-tag">
                  {item.interpretacion.metrica.replaceAll('_', ' ')}
                  {filtrosTexto && ` · ${filtrosTexto}`}
                </div>
              ) : (
                <div className="report-dashboard-tag report-dashboard-tag-fail">{item.motivo}</div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
