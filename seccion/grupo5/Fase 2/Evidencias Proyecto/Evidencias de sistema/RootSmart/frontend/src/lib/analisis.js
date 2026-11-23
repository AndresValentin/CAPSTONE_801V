// Ayudas para mostrar la comparación de períodos y la proyección que calcula el
// backend (backend/app/analisis.py). Aquí no se calcula nada: solo se da formato.

const PORCENTAJE = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1, minimumFractionDigits: 1 })

export const OPCIONES_COMPARAR = [
  ['', 'Sin comparar'],
  ['periodo_anterior', 'Período anterior'],
  ['anio_anterior', 'Mismo período del año anterior'],
]

// Comparación que sí se calculó (no omitida)
export function comparacionActiva(resultado) {
  const c = resultado?.comparacion
  return c && !c.omitida ? c : null
}

export function textoVariacion(variacion) {
  if (variacion === null || variacion === undefined) return 'sin base para comparar'
  const signo = variacion > 0 ? '+' : variacion < 0 ? '−' : ''
  return `${signo}${PORCENTAJE.format(Math.abs(variacion))} %`
}

// Variación sin signo, para frases como "sube 12,0 %"
export function textoVariacionAbsoluta(variacion) {
  return `${PORCENTAJE.format(Math.abs(variacion))} %`
}

// La flecha y el texto dicen la dirección; el color solo dice si es buena noticia
export function sentidoVariacion(variacion, mejorSiBaja) {
  if (!variacion) return { flecha: '→', clase: 'variacion-neutra', lectura: 'sin cambio' }
  const sube = variacion > 0
  const buena = mejorSiBaja ? !sube : sube
  return { flecha: sube ? '▲' : '▼', clase: buena ? 'variacion-buena' : 'variacion-mala', lectura: sube ? 'sube' : 'baja' }
}

// Serie de un gráfico por mes con la proyección y los meses atípicos que calculó el
// backend: columnas extra `proyectado`, `rango` ([mín, máx]) y `atipico`.
export function serieConAnalisis(serie, proyeccion) {
  const atipicos = new Set((proyeccion?.anomalias ?? []).map((a) => a.mes))
  const filas = serie.map((f) => ({ ...f, atipico: atipicos.has(f.categoria) ? f.valor : null }))
  if (!proyeccion?.meses?.length) return filas
  // La línea proyectada parte del último mes real usado para entrenar el modelo
  const base = filas.find((f) => f.categoria === proyeccion.base.hasta)
  if (base) Object.assign(base, { proyectado: base.valor, rango: [base.valor, base.valor] })
  proyeccion.meses.forEach((p) => {
    const existente = filas.find((f) => f.categoria === p.mes)
    const extra = { proyectado: p.valor, rango: [p.min, p.max] }
    if (existente) Object.assign(existente, extra)
    else filas.push({ categoria: p.mes, ...extra })
  })
  return filas
}
