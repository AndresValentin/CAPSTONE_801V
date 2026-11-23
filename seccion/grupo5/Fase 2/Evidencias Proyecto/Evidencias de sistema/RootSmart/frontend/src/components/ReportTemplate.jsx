import { LayoutDashboard, FileStack, CircleDollarSign, TrendingUp, MessageSquareText, BarChart3 } from 'lucide-react'
import './ReportTemplate.css'

const KPIS = [
  { icono: FileStack, etiqueta: 'Siniestros', clase: 'kpi-icon-blue' },
  { icono: CircleDollarSign, etiqueta: 'Monto pagado total', clase: 'kpi-icon-teal' },
  { icono: TrendingUp, etiqueta: 'Monto promedio', clase: 'kpi-icon-amber' },
]

// Plantilla vacía del reporte: muestra el formato en que aparecerá el
// resultado. El reporte se genera pidiéndolo en el chat.
export default function ReportTemplate() {
  return (
    <section className="report-template">
      <div className="panel-title-row">
        <div>
          <h2 className="tpl-title"><LayoutDashboard size={16} strokeWidth={2.4} /> Reporte sin generar</h2>
          <p className="panel-subtitle">El título, los filtros y el tipo de gráfico se completan según lo que pidas en el chat.</p>
        </div>
        <span className="tpl-badge">Plantilla</span>
      </div>

      <div className="kpi-row">
        {KPIS.map(({ icono: Icono, etiqueta, clase }) => (
          <div key={etiqueta} className="kpi-card tpl-kpi">
            <span className={`kpi-icon ${clase}`}><Icono size={16} /></span>
            <span className="kpi-label">{etiqueta}</span>
            <span className="kpi-value tpl-placeholder">—</span>
          </div>
        ))}
      </div>

      <div className="tpl-chart">
        <BarChart3 size={34} strokeWidth={1.6} />
        <p className="tpl-chart-title">Aquí aparecerá tu gráfico</p>
        <p className="tpl-chart-hint">
          <MessageSquareText size={14} />
          Pídelo en el chat, por ejemplo: <em>“genera un reporte del monto pagado por región en barras”</em>
        </p>
      </div>

      <div className="tpl-table">
        <span className="tpl-table-title">Detalle de siniestros</span>
        {[0, 1, 2].map((i) => (
          <div key={i} className="tpl-row">
            <span /><span /><span /><span />
          </div>
        ))}
      </div>
    </section>
  )
}
