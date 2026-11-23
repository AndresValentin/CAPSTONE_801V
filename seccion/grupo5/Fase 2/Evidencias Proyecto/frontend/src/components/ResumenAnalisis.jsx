import { AlertTriangle, ArrowLeftRight, Info, TrendingUp } from 'lucide-react'
import { sentidoVariacion, textoVariacion } from '../lib/analisis.js'
import { formatMetrica } from '../lib/formato.js'
import './ResumenAnalisis.css'

function Avisos({ textos }) {
  if (!textos?.length) return null
  return (
    <details className="analisis-avisos">
      <summary>{textos.length === 1 ? '1 aviso' : `${textos.length} avisos`} para leer bien este resultado</summary>
      <ul>
        {textos.map((t) => <li key={t}><AlertTriangle size={12} /> {t}</li>)}
      </ul>
    </details>
  )
}

function Comparacion({ c, fmt }) {
  if (c.omitida) {
    return <p className="analisis-omitida"><Info size={13} /> {c.omitida}</p>
  }
  const sentido = sentidoVariacion(c.variacion, c.mejorSiBaja)
  return (
    <div className="analisis-bloque">
      <p className="analisis-titulo"><ArrowLeftRight size={13} /> {c.titulo} · {c.desde} a {c.hasta}</p>
      <p className="analisis-linea">
        <span className={`analisis-variacion ${sentido.clase}`}>{sentido.flecha} {textoVariacion(c.variacion)}</span>
        {' '}frente a {fmt(c.total)}
      </p>
      <Avisos textos={c.advertencias} />
    </div>
  )
}

function Proyeccion({ p, fmt }) {
  if (p.omitida) {
    return <p className="analisis-omitida"><Info size={13} /> {p.omitida}</p>
  }
  const [siguiente, ...resto] = p.meses
  const r2 = p.r2.toLocaleString('es-CL', { maximumFractionDigits: 2 })
  const avisos = [
    ...p.anomalias.map((a) => `Mes atípico: ${a.mes} registró ${fmt(a.valor)} y la tendencia esperaba ${fmt(a.esperado)}.`),
    ...p.notas,
  ]
  return (
    <div className="analisis-bloque">
      <p className="analisis-titulo"><TrendingUp size={13} /> Proyección por regresión lineal</p>
      <p className="analisis-linea">
        {siguiente.mes}: <strong>{fmt(siguiente.valor)}</strong>
        <span className="analisis-rango"> (entre {fmt(siguiente.min)} y {fmt(siguiente.max)})</span>
      </p>
      {resto.length > 0 && (
        <p className="analisis-secundario">{resto.map((m) => `${m.mes}: ${fmt(m.valor)}`).join(' · ')}</p>
      )}
      <p className="analisis-secundario">
        Tendencia {p.pendiente >= 0 ? '+' : ''}{fmt(p.pendiente)} por mes · R² {r2} · {p.base.meses} meses ({p.base.desde} a {p.base.hasta})
      </p>
      <Avisos textos={avisos} />
    </div>
  )
}

// Explica en palabras la comparación y la proyección que calculó el backend.
// Si alguna no corresponde (por ejemplo, comparar la reserva), muestra el motivo.
export default function ResumenAnalisis({ resultado, esMoneda }) {
  const c = resultado?.comparacion
  const p = resultado?.proyeccion
  if (!c && !p) return null
  const fmt = (v) => formatMetrica(v, esMoneda)
  return (
    <div className="analisis">
      {c && <Comparacion c={c} fmt={fmt} />}
      {p && <Proyeccion p={p} fmt={fmt} />}
    </div>
  )
}
