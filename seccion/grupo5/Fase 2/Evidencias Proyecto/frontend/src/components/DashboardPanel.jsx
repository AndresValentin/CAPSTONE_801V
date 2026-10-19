import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { LayoutDashboard, FileStack, CircleDollarSign, TrendingUp } from 'lucide-react'
import {
  METRICAS, DIMENSIONES, VISUALIZACIONES, agregarPor, completarReporte, totalMetrica,
} from '../data/mockData.js'
import { formatCLP, formatCLPCorto, formatMetrica } from '../lib/formato.js'
import './DashboardPanel.css'

const COLORS = ['#1e2a5e', '#14b8a6', '#2563eb', '#d97706', '#7c3aed']
const ETIQUETA_FILTRO = { producto: 'Producto', region: 'Región', estado: 'Estado', desde: 'Desde', hasta: 'Hasta' }

// También lo usa ReporteBD para dibujar los reportes que vienen del backend
export function GraficoPrincipal({ visualizacion, serie, total, esMoneda, cantidad, unidad = 'siniestros' }) {
  const fmt = (v) => formatMetrica(v, esMoneda)
  const fmtEje = (v) => (esMoneda ? formatCLPCorto(v) : v)

  if (visualizacion === 'kpi') {
    return (
      <div className="report-kpi">
        <span className="report-kpi-value">{fmt(total)}</span>
        <span className="report-kpi-caption">calculado sobre {cantidad} {unidad}</span>
      </div>
    )
  }

  if (visualizacion === 'tabla') {
    const suma = serie.reduce((acc, f) => acc + f.valor, 0)
    return (
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Categoría</th><th className="num">Valor</th><th className="num">% del total</th></tr>
          </thead>
          <tbody>
            {serie.map((f) => (
              <tr key={f.categoria}>
                <td>{f.categoria}</td>
                <td className="num">{fmt(f.valor)}</td>
                <td className="num">{suma ? ((f.valor / suma) * 100).toFixed(1) : 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (visualizacion === 'torta') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={serie} dataKey="valor" nameKey="categoria" innerRadius={70} outerRadius={110} paddingAngle={2}>
            {serie.map((f, i) => <Cell key={f.categoria} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v) => fmt(v)} />
          <Legend verticalAlign="middle" align="right" layout="vertical" iconType="circle" />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (visualizacion === 'lineas') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={serie} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
          <XAxis dataKey="categoria" tick={{ fontSize: 12 }} tickLine={false} />
          <YAxis tick={{ fontSize: 12 }} tickFormatter={fmtEje} allowDecimals={false} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => fmt(v)} />
          <Line type="monotone" dataKey="valor" name="Valor" stroke="#14b8a6" strokeWidth={2.5} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={serie} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
        <XAxis dataKey="categoria" tick={{ fontSize: 12 }} tickLine={false} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={fmtEje} allowDecimals={false} tickLine={false} axisLine={false} />
        <Tooltip formatter={(v) => fmt(v)} cursor={{ fill: '#f4f6fb' }} />
        <Bar dataKey="valor" name="Valor" fill="#1e2a5e" radius={[6, 6, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function DashboardPanel({ datos, filtros, reporte }) {
  const { metrica, agruparPor, visualizacion } = completarReporte(reporte.interpretacion)
  const { etiqueta, moneda } = METRICAS[metrica]
  const serie = agruparPor === 'ninguno' ? [] : agregarPor(datos, agruparPor, metrica)

  const montoTotal = totalMetrica(datos, 'monto_pagado_total')
  const montoPromedio = totalMetrica(datos, 'monto_promedio')
  const filtrosActivos = Object.entries(filtros).filter(([, v]) => v && v !== 'Todos' && v !== 'Todas')
  const tituloGrafico = agruparPor === 'ninguno' ? etiqueta : `${etiqueta} por ${DIMENSIONES[agruparPor].toLowerCase()}`

  return (
    <section className="dashboard-panel">
      <div className="panel-title-row">
        <div className="report-heading">
          <h2><LayoutDashboard size={16} strokeWidth={2.4} /> {reporte.pregunta}</h2>
          <p className="panel-subtitle">
            {etiqueta} · {DIMENSIONES[agruparPor]} · {VISUALIZACIONES[visualizacion]} · {reporte.interpretacion.catalogoVersion}
          </p>
        </div>
        <span className="badge badge-validado">Solicitud validada</span>
      </div>

      {filtrosActivos.length > 0 && (
        <div className="active-filters">
          {filtrosActivos.map(([k, v]) => (
            <span key={k} className="filter-chip">{ETIQUETA_FILTRO[k] ?? k}: {v}</span>
          ))}
        </div>
      )}

      <div className="kpi-row">
        <div className={`kpi-card ${metrica === 'cantidad_siniestros' ? 'kpi-card-main' : ''}`}>
          <span className="kpi-icon kpi-icon-blue"><FileStack size={16} /></span>
          <span className="kpi-label">Siniestros</span>
          <span className="kpi-value">{datos.length}</span>
        </div>
        <div className={`kpi-card ${metrica === 'monto_pagado_total' ? 'kpi-card-main' : ''}`}>
          <span className="kpi-icon kpi-icon-teal"><CircleDollarSign size={16} /></span>
          <span className="kpi-label">Monto pagado total</span>
          <span className="kpi-value">{formatCLP(montoTotal)}</span>
        </div>
        <div className={`kpi-card ${metrica === 'monto_promedio' ? 'kpi-card-main' : ''}`}>
          <span className="kpi-icon kpi-icon-amber"><TrendingUp size={16} /></span>
          <span className="kpi-label">Monto promedio</span>
          <span className="kpi-value">{formatCLP(montoPromedio)}</span>
        </div>
      </div>

      <div className="chart-card chart-card-main">
        <h3>{tituloGrafico}</h3>
        {datos.length === 0
          ? <p className="chart-empty">No hay siniestros con los filtros actuales.</p>
          : (
            <GraficoPrincipal
              visualizacion={visualizacion}
              serie={serie}
              total={totalMetrica(datos, metrica)}
              esMoneda={moneda}
              cantidad={datos.length}
            />
          )}
      </div>

      <section className="table-card">
        <h3 className="table-card-title">Detalle de siniestros <span>{datos.length} {datos.length === 1 ? 'registro' : 'registros'}</span></h3>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Siniestro</th>
                <th>Póliza</th>
                <th>Producto</th>
                <th>Región</th>
                <th>Estado</th>
                <th>Fecha</th>
                <th className="num">Monto</th>
              </tr>
            </thead>
            <tbody>
              {datos.slice(0, 50).map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.poliza}</td>
                  <td>{s.producto}</td>
                  <td>{s.region}</td>
                  <td><span className={`status-pill status-${s.estado.replace(' ', '-')}`}>{s.estado}</span></td>
                  <td>{s.fecha}</td>
                  <td className="num">{formatCLP(s.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {datos.length > 50 && <p className="table-more">Mostrando 50 de {datos.length} registros.</p>}
        </div>
      </section>
    </section>
  )
}
