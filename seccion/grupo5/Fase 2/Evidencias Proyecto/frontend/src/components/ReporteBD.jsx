import { LayoutDashboard, Database, Hash } from 'lucide-react'
import { GraficoPrincipal } from './DashboardPanel.jsx'
import { VISUALIZACIONES } from '../data/mockData.js'
import { formatCLP, formatMetrica } from '../lib/formato.js'
import './DashboardPanel.css'

function formatCelda(valor, esMoneda) {
  if (valor === null || valor === undefined) return '—'
  return esMoneda ? formatCLP(valor) : String(valor)
}

// Reporte armado con los datos que devolvió el backend (SQL Server).
// A diferencia de DashboardPanel, no calcula nada: solo dibuja `resultado`.
export default function ReporteBD({ reporte, actualizando = false }) {
  const { interpretacion: i, resultado: r } = reporte
  const sinAgrupar = i.agruparPor === 'ninguno' || r.serie.length === 0
  const visualizacion = sinAgrupar ? 'kpi' : i.visualizacion
  const tituloGrafico = sinAgrupar ? i.metricaEtiqueta : `${i.metricaEtiqueta} por ${i.dimensionEtiqueta.toLowerCase()}`
  const chips = [
    ...i.filtros.map((f) => [f.etiqueta, f.valor]),
    ...(i.desde ? [['Desde', i.desde]] : []),
    ...(i.hasta ? [['Hasta', i.hasta]] : []),
  ]
  const moneda = new Set(r.detalle.columnasMoneda)

  return (
    <section className={`dashboard-panel ${actualizando ? 'dashboard-panel-actualizando' : ''}`} aria-busy={actualizando}>
      <div className="panel-title-row">
        <div className="report-heading">
          <h2><LayoutDashboard size={16} strokeWidth={2.4} /> {reporte.pregunta}</h2>
          <p className="panel-subtitle">
            {i.dominio} · {i.metricaEtiqueta} · {i.dimensionEtiqueta} · {VISUALIZACIONES[i.visualizacion] ?? i.visualizacion} · {i.catalogoVersion}
          </p>
        </div>
        <span className="badge badge-validado">Solicitud validada</span>
      </div>

      {chips.length > 0 && (
        <div className="active-filters">
          {chips.map(([k, v]) => <span key={k} className="filter-chip">{k}: {v}</span>)}
        </div>
      )}

      <div className="kpi-row">
        <div className="kpi-card kpi-card-main">
          <span className="kpi-icon kpi-icon-teal"><Database size={16} /></span>
          <span className="kpi-label">{i.metricaEtiqueta}</span>
          <span className="kpi-value">{formatMetrica(r.total, i.moneda)}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-icon kpi-icon-blue"><Hash size={16} /></span>
          <span className="kpi-label">Registros considerados</span>
          <span className="kpi-value">{r.cantidad}</span>
        </div>
      </div>

      <div className="chart-card chart-card-main">
        <h3>{tituloGrafico}</h3>
        {r.cantidad === 0
          ? <p className="chart-empty">No hay registros con los filtros de esta solicitud.</p>
          : (
            <GraficoPrincipal
              visualizacion={visualizacion}
              serie={r.serie}
              total={r.total}
              esMoneda={i.moneda}
              cantidad={r.cantidad}
              unidad="registros"
            />
          )}
      </div>

      <section className="table-card">
        <h3 className="table-card-title">
          Detalle de registros
          <span>
            {r.detalle.filas.length < r.cantidad
              ? `${r.detalle.filas.length} más recientes de ${r.cantidad}`
              : `${r.cantidad} ${r.cantidad === 1 ? 'registro' : 'registros'}`}
          </span>
        </h3>
        {r.detalle.filas.length === 0
          ? <p className="chart-empty">No hay registros con los filtros de esta solicitud.</p>
          : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {r.detalle.columnas.map((c) => <th key={c} className={moneda.has(c) ? 'num' : undefined}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {r.detalle.filas.map((fila, n) => (
                  <tr key={n}>
                    {r.detalle.columnas.map((c) => (
                      <td key={c} className={moneda.has(c) ? 'num' : undefined}>{formatCelda(fila[c], moneda.has(c))}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
      </section>
    </section>
  )
}
