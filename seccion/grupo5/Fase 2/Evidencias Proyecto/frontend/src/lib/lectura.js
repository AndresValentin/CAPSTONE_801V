// "Lo que dice el gráfico" en una o dos frases, calculado con los mismos datos que se
// dibujan (sin IA, así que no inventa nada): la cifra contra el período anterior, el
// último mes contra el anterior o qué categoría concentra el total.
import { comparacionActiva, sentidoVariacion, textoVariacion, textoVariacionAbsoluta } from './analisis.js'
import { formatMetrica } from './formato.js'

const PORCENTAJE = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 })

function variacion(actual, anterior) {
  return anterior ? ((actual - anterior) / Math.abs(anterior)) * 100 : null
}

// La cifra y su variación ya están grandes en la tarjeta: aquí va el período con que se
// comparó y si el cambio es bueno o malo para el negocio
function lecturaKpi(r) {
  const c = comparacionActiva(r)
  if (!c || c.variacion === null || c.variacion === undefined) return null
  const { lectura, clase } = sentidoVariacion(c.variacion, c.mejorSiBaja)
  const periodo = c.desde === c.hasta ? c.desde : `${c.desde} a ${c.hasta}`
  if (lectura === 'sin cambio') return `Igual que en ${periodo}.`
  const verbo = lectura === 'sube' ? 'Subió' : 'Bajó'
  const juicio = clase === 'variacion-buena' ? 'es una buena señal' : 'conviene revisarlo'
  return `${verbo} ${textoVariacionAbsoluta(c.variacion)} respecto de ${periodo}: ${juicio}.`
}

function lecturaMensual(serie, fmt) {
  const meses = serie.filter((f) => f.categoria)
  if (meses.length < 2) return null
  const ultimo = meses.at(-1)
  const previo = meses.at(-2)
  const maximo = meses.reduce((a, b) => (b.valor > a.valor ? b : a))
  const v = variacion(ultimo.valor, previo.valor)
  const cambio = v === null ? '' : ` (${textoVariacion(v)} frente a ${previo.categoria})`
  const pico = maximo === ultimo
    ? 'Es el mes más alto del gráfico.'
    : `El mes más alto fue ${maximo.categoria}, con ${fmt(maximo.valor)}.`
  return `En ${ultimo.categoria}: ${fmt(ultimo.valor)}${cambio}. ${pico}`
}

function lecturaCategorias(serie, fmt) {
  const filas = serie.filter((f) => f.categoria && f.valor > 0).sort((a, b) => b.valor - a.valor)
  const total = filas.reduce((suma, f) => suma + f.valor, 0)
  if (filas.length < 2 || total <= 0) return null
  const [primera] = filas
  const parte = (primera.valor / total) * 100
  if (filas.length >= 4 && parte < 25) {
    return `El total está repartido: ninguna categoría supera el 25 %. La mayor es ${primera.categoria} (${fmt(primera.valor)}).`
  }
  const texto = `${primera.categoria} concentra el ${PORCENTAJE.format(parte)} % del total (${fmt(primera.valor)}).`
  if (filas.length <= 3) return texto
  const tres = (filas.slice(0, 3).reduce((suma, f) => suma + f.valor, 0) / total) * 100
  return `${texto} Las 3 primeras suman el ${PORCENTAJE.format(tres)} %.`
}

export function lecturaGrafico(reporte) {
  const { interpretacion: i, resultado: r } = reporte
  if (!i || !r || !r.cantidad) return null
  const fmt = (v) => formatMetrica(v, i.moneda)
  if (i.agruparPor === 'ninguno' || r.serie.length === 0) return lecturaKpi(r)
  if (i.agruparPor === 'mes') return lecturaMensual(r.serie, fmt)
  return lecturaCategorias(r.serie, fmt)
}
