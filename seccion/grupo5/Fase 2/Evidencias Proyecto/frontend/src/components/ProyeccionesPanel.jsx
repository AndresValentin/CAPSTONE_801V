import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, LayoutDashboard, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react'
import { claveSerie } from '../hooks/useProyecciones.js'
import { serieConAnalisis } from '../lib/analisis.js'
import { formatCLPCorto, formatMetrica } from '../lib/formato.js'
import { ESTILO_TOOLTIP } from '../lib/graficos.js'
import './MLPanel.css'

const MESES_EN_GRAFICO = 24

function Selector({ p }) {
  const areas = [...new Set(p.series.map((s) => s.area))]
  return (
    <select className="proy-select" aria-label="Qué proyectar" value={p.elegida} onChange={(e) => p.elegir(e.target.value)}>
      {areas.map((area) => (
        <optgroup key={area} label={area}>
          {p.series.filter((s) => s.area === area).map((s) => (
            <option key={claveSerie(s)} value={claveSerie(s)}>{s.recomendada ? '★ ' : ''}{s.etiqueta}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

// Módulo "Proyecciones" del menú lateral (modo backend): regresión lineal por mínimos
// cuadrados sobre toda la serie mensual de la BD, calculada en backend/app/analisis.py.
// `p` = useProyecciones(); `onVerEnReporte` agrega la serie y su proyección al chat.
export default function ProyeccionesPanel({ p, onVerEnReporte }) {
  if (p.series === null) {
    return p.error
      ? <p className="ml-empty">{p.error}</p>
      : <p className="ml-empty">Cargando las series disponibles…</p>
  }
  if (p.series.length === 0) {
    return <p className="ml-empty">Tus áreas no tienen métricas que se puedan proyectar.</p>
  }

  const respuesta = p.respuesta
  const proyeccion = respuesta?.resultado?.proyeccion
  const fmt = (v) => formatMetrica(v, p.serie?.moneda)
  const fmtEje = (v) => (p.serie?.moneda ? formatCLPCorto(v) : v.toLocaleString('es-CL'))

  return (
    <div className="ml-panel">
      <Selector p={p} />
      {p.serie?.motivo && <p className="module-hint proy-motivo">{p.serie.motivo}</p>}

      {p.cargando && <p className="ml-empty">Calculando con los datos de la base…</p>}
      {p.error && <p className="ml-empty proy-error" role="alert">{p.error}</p>}
      {!p.cargando && proyeccion?.omitida && <p className="ml-empty">{proyeccion.omitida}</p>}

      {!p.cargando && proyeccion && !proyeccion.omitida && (() => {
        const datos = serieConAnalisis(respuesta.resultado.serie.slice(-MESES_EN_GRAFICO), proyeccion)
        const [siguiente, ...resto] = proyeccion.meses
        const sube = proyeccion.pendiente >= 0
        const avisos = [
          ...proyeccion.anomalias.map((a) => `${a.mes} fue atípico: ${fmt(a.valor)} (se esperaba ${fmt(a.esperado)}).`),
          ...proyeccion.notas,
        ]
        return (
          <>
            <ResponsiveContainer width="100%" height={120}>
              <ComposedChart data={datos} margin={{ top: 4, right: 4, left: -14, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="categoria" tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} interval="preserveStartEnd" tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} tickFormatter={fmtEje} tickLine={false} axisLine={false} width={44} />
                <Tooltip
                  {...ESTILO_TOOLTIP}
                  formatter={(v) => (Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])}` : v == null ? '—' : fmt(v))}
                />
                <Area dataKey="rango" name="Rango probable" stroke="none" fill="var(--chart-proyeccion)" fillOpacity={0.15} isAnimationActive={false} />
                <Line dataKey="valor" name="Real" stroke="var(--color-primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="proyectado" name="Proyectado" stroke="var(--chart-proyeccion)" strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2 }} isAnimationActive={false} />
                <Scatter dataKey="atipico" name="Mes atípico" fill="var(--color-danger)" isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>

            <div className="ml-forecast">
              {sube ? <TrendingUp size={14} className="ml-trend-up" /> : <TrendingDown size={14} className="ml-trend-down" />}
              <div>
                <span className="ml-forecast-label">Proyección {siguiente.mes}</span>
                <strong className="ml-forecast-value">{fmt(siguiente.valor)}</strong>
                <span className="proy-rango">entre {fmt(siguiente.min)} y {fmt(siguiente.max)}</span>
              </div>
            </div>
            {resto.length > 0 && (
              <p className="proy-siguientes">{resto.map((m) => `${m.mes}: ${fmt(m.valor)}`).join(' · ')}</p>
            )}

            <div className="ml-stats">
              <span title="Cuánto explica la tendencia de la variación mensual">R² {proyeccion.r2.toLocaleString('es-CL', { maximumFractionDigits: 2 })}</span>
              <span>{sube ? '+' : ''}{fmt(proyeccion.pendiente)}/mes</span>
            </div>

            {avisos.length > 0 && (
              <details className="proy-avisos">
                <summary><AlertTriangle size={11} /> {avisos.length === 1 ? '1 aviso' : `${avisos.length} avisos`}</summary>
                <ul>{avisos.map((a) => <li key={a}>{a}</li>)}</ul>
              </details>
            )}

            <div className="proy-acciones">
              <button type="button" className="proy-boton" onClick={() => onVerEnReporte(respuesta, p.serie)}>
                <LayoutDashboard size={13} /> Ver en el reporte
              </button>
              <button type="button" className="proy-boton proy-boton-icono" title="Volver a calcular con los datos actuales" aria-label="Volver a calcular" onClick={p.recalcular}>
                <RefreshCw size={13} />
              </button>
            </div>
            <p className="ml-disclaimer">
              Regresión lineal sobre {proyeccion.base.meses} meses completos de la base ({proyeccion.base.desde} a {proyeccion.base.hasta}).
              El rango cubre ±2 errores estándar; los meses atípicos no tuercen la tendencia.
            </p>
          </>
        )
      })()}
    </div>
  )
}
