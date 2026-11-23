import { ESTILO_TOOLTIP } from '../lib/graficos.js'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { LayoutDashboard, FileStack, CircleDollarSign, TrendingUp } from 'lucide-react'
import {
  METRICAS, DIMENSIONES, VISUALIZACIONES, agregarPor, completarReporte, totalMetrica,
} from '../data/mockData.js'
import { formatCLP, formatCLPCorto, formatMetrica } from '../lib/formato.js'
import MapaChile from './MapaChile.jsx'
import './DashboardPanel.css'

// Paleta validada para contraste y daltonismo. El color nunca se repite: si hay
// más categorías que colores, las menores se agrupan en "Otros".
const COLORS = ['var(--serie-1)', 'var(--serie-2)', 'var(--serie-3)', 'var(--serie-4)', 'var(--serie-5)']
const COLOR_OTROS = 'var(--serie-otros)'
const ETIQUETA_FILTRO = { producto: 'Producto', region: 'Región', estado: 'Estado', desde: 'Desde', hasta: 'Hasta' }

function agruparOtros(serie) {
  if (serie.length <= COLORS.length) return serie
  const orden = [...serie].sort((a, b) => b.valor - a.valor)
  const resto = orden.slice(COLORS.length - 1)
  return [
    ...orden.slice(0, COLORS.length - 1),
    { categoria: `Otros (${resto.length})`, valor: resto.reduce((acc, f) => acc + f.valor, 0), otros: true },
  ]
}

// También lo usa ReporteBD para dibujar los reportes que vienen del backend, y
// ReporteGraficos con `compacto` para que quepan varios gráficos en pantalla
export function GraficoPrincipal({ visualizacion, serie, total, esMoneda, cantidad, unidad = 'siniestros', compacto = false, altura }) {
  const fmt = (v) => formatMetrica(v, esMoneda)
  const fmtEje = (v) => (esMoneda ? formatCLPCorto(v) : v)
  const alto = altura ?? (compacto ? 240 : 300)
  // En una grilla de varios gráficos la animación solo distrae al redimensionar
  const animar = !compacto && altura === undefined
  const radioExterior = Math.round(alto * 0.36)

  if (visualizacion === 'mapa') {
    return <MapaChile serie={serie} esMoneda={esMoneda} altura={Math.max(alto, 560)} />
  }

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
    const porciones = agruparOtros(serie)
    return (
      <ResponsiveContainer width="100%" height={alto}>
        <PieChart>
          <Pie
            data={porciones}
            dataKey="valor"
            nameKey="categoria"
            innerRadius={Math.round(radioExterior * 0.64)}
            outerRadius={radioExterior}
            paddingAngle={2}
            stroke="var(--color-surface)"
            isAnimationActive={animar}
          >
            {porciones.map((f, i) => <Cell key={f.categoria} fill={f.otros ? COLOR_OTROS : COLORS[i]} />)}
          </Pie>
          <Tooltip {...ESTILO_TOOLTIP} formatter={(v) => fmt(v)} />
          <Legend
            verticalAlign="middle"
            align="right"
            layout="vertical"
            iconType="circle"
            wrapperStyle={{ fontSize: 12 }}
            formatter={(nombre) => <span style={{ color: 'var(--color-text)' }}>{nombre}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (visualizacion === 'lineas') {
    return (
      <ResponsiveContainer width="100%" height={alto}>
        <LineChart data={serie} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="categoria" tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} minTickGap={24} />
          <YAxis tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickFormatter={fmtEje} allowDecimals={false} tickLine={false} axisLine={false} width={compacto ? 62 : 60} />
          <Tooltip {...ESTILO_TOOLTIP} formatter={(v) => fmt(v)} />
          <Line
            type="monotone"
            dataKey="valor"
            name="Valor"
            stroke="var(--chart-linea)"
            strokeWidth={2}
            dot={serie.length > 18 ? false : { r: 4 }}
            activeDot={{ r: 5 }}
            isAnimationActive={animar}
          />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  // En tarjetas angostas las barras van horizontales para que las etiquetas se lean completas
  if (compacto) {
    return (
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={serie} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 0 }} barCategoryGap="22%">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} tickFormatter={fmtEje} tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="categoria" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} tickLine={false} width={118} interval={0} />
          <Tooltip {...ESTILO_TOOLTIP} formatter={(v) => fmt(v)} cursor={{ fill: 'var(--chart-cursor)' }} />
          <Bar dataKey="valor" name="Valor" fill="var(--chart-barra)" radius={[0, 4, 4, 0]} maxBarSize={30} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={serie} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey="categoria" tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} />
        <YAxis tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickFormatter={fmtEje} allowDecimals={false} tickLine={false} axisLine={false} />
        <Tooltip {...ESTILO_TOOLTIP} formatter={(v) => fmt(v)} cursor={{ fill: 'var(--chart-cursor)' }} />
        <Bar dataKey="valor" name="Valor" fill="var(--chart-barra)" radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive={animar} />
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
