import { useEffect, useId, useState } from 'react'
import { obtenerMapaChile } from '../lib/api.js'
import { formatCLPCorto, formatMetrica } from '../lib/formato.js'
import './MapaChile.css'

const COLOR_SIN_DATOS = 'var(--mapa-vacio)'
const SEPARACION_ETIQUETAS = 46
const ANCHO_ETIQUETAS = 180

// Mezcla entre los dos colores del tema activo, así el mapa cambia junto con el modo oscuro
function colorDe(valor, min, max) {
  const t = max > min ? (valor - min) / (max - min) : 1
  return `color-mix(in srgb, var(--mapa-alto) ${Math.round(t * 100)}%, var(--mapa-bajo))`
}

// Reparte las etiquetas junto a su región sin que se monten entre ellas
function ubicarEtiquetas(items, alto) {
  const ubicadas = [...items].sort((a, b) => a.y - b.y).map((it) => ({ ...it }))
  ubicadas.forEach((it, i) => {
    it.yEtiqueta = Math.max(it.y, i ? ubicadas[i - 1].yEtiqueta + SEPARACION_ETIQUETAS : 24)
  })
  for (let i = ubicadas.length - 1, tope = alto - 70; i >= 0; i--, tope -= SEPARACION_ETIQUETAS) {
    ubicadas[i].yEtiqueta = Math.min(ubicadas[i].yEtiqueta, tope)
  }
  return ubicadas
}

// Mapa de Chile por región. El color y la etiqueta salen del valor de cada región.
export default function MapaChile({ serie, esMoneda, altura = 560 }) {
  const [mapa, setMapa] = useState(null)
  const [error, setError] = useState(false)
  const [tip, setTip] = useState(null)
  const degradado = `degradado${useId().replace(/\W/g, '')}`

  useEffect(() => {
    let vigente = true
    obtenerMapaChile()
      .then((m) => { if (vigente) setMapa(m) })
      .catch(() => { if (vigente) setError(true) })
    return () => { vigente = false }
  }, [])

  if (error) return <p className="chart-empty">No se pudo cargar el mapa de Chile.</p>
  if (!mapa) return <p className="chart-empty">Cargando mapa…</p>

  const k = (altura - 16) / mapa.alto
  const anchoMapa = mapa.ancho * k
  const xEtiquetas = Math.round(anchoMapa + 56)
  const ancho = xEtiquetas + ANCHO_ETIQUETAS
  const porRegion = new Map(serie.map((f) => [f.categoria, f.valor]))
  const valores = serie.map((f) => f.valor)
  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const conDatos = mapa.regiones
    .filter((r) => porRegion.has(r.nombre))
    .map((r) => ({ ...r, valor: porRegion.get(r.nombre), x: r.cx * k + 8, y: r.cy * k + 8 }))
  const etiquetas = ubicarEtiquetas(conDatos, altura)

  function mostrar(e, nombre, tiene, valor) {
    const caja = e.currentTarget.ownerSVGElement.parentElement.getBoundingClientRect()
    setTip({
      x: e.clientX - caja.left + 12,
      y: e.clientY - caja.top + 12,
      nombre,
      texto: tiene ? formatMetrica(valor, esMoneda) : 'Sin datos',
    })
  }

  return (
    <div className="mapa-chile">
      <svg viewBox={`0 0 ${ancho} ${altura}`} width={ancho} height={altura} role="img" aria-label="Mapa de Chile por región">
        <defs>
          <linearGradient id={degradado}>
            <stop offset="0%" style={{ stopColor: colorDe(min, min, max) }} />
            <stop offset="100%" style={{ stopColor: colorDe(max, min, max) }} />
          </linearGradient>
        </defs>
        <g transform={`translate(8 8) scale(${k})`}>
          {mapa.regiones.map((r) => {
            const tiene = porRegion.has(r.nombre)
            return (
              <path
                key={r.nombre}
                className="mapa-region"
                d={r.d}
                style={{ fill: tiene ? colorDe(porRegion.get(r.nombre), min, max) : COLOR_SIN_DATOS }}
                onPointerMove={(e) => mostrar(e, r.nombre, tiene, porRegion.get(r.nombre))}
                onPointerLeave={() => setTip(null)}
              />
            )
          })}
        </g>
        {etiquetas.map((r) => (
          <g key={r.nombre}>
            <polyline className="mapa-guia" points={`${r.x},${r.y} ${xEtiquetas - 18},${r.yEtiqueta} ${xEtiquetas - 6},${r.yEtiqueta}`} />
            <circle className="mapa-punto" cx={r.x} cy={r.y} r="2.5" />
            <text className="mapa-nombre" x={xEtiquetas} y={r.yEtiqueta - 3}>{r.nombre}</text>
            <text className="mapa-valor" x={xEtiquetas} y={r.yEtiqueta + 14}>
              {esMoneda ? formatCLPCorto(r.valor) : formatMetrica(r.valor, false)}
            </text>
          </g>
        ))}
        <g transform={`translate(${xEtiquetas} ${altura - 42})`}>
          <rect width="120" height="8" rx="4" fill={`url(#${degradado})`} />
          <text className="mapa-escala" y="22">{esMoneda ? formatCLPCorto(min) : formatMetrica(min, false)}</text>
          <text className="mapa-escala" x="120" y="22" textAnchor="end">{esMoneda ? formatCLPCorto(max) : formatMetrica(max, false)}</text>
          <rect x="132" y="0" width="10" height="8" rx="2" fill={COLOR_SIN_DATOS} />
          <text className="mapa-escala" x="132" y="22">Sin datos</text>
        </g>
      </svg>
      {tip && (
        <div className="mapa-tip" style={{ left: tip.x, top: tip.y }} role="status">
          <strong>{tip.nombre}</strong>
          {tip.texto}
        </div>
      )}
    </div>
  )
}
