const CLP = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 })
const NUMERO = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 })

export function formatCLP(valor) {
  return CLP.format(valor)
}

// $7,6 M — para ejes de gráficos y resúmenes cortos
export function formatCLPCorto(valor) {
  if (Math.abs(valor) >= 1e6) return `$${(valor / 1e6).toLocaleString('es-CL', { maximumFractionDigits: 1 })} M`
  if (Math.abs(valor) >= 1e3) return `$${Math.round(valor / 1e3).toLocaleString('es-CL')} mil`
  return CLP.format(valor)
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
  'octubre', 'noviembre', 'diciembre']

// '2026-04' -> 'abril 2026'
export function nombreMes(mes) {
  const [anio, numero] = (mes ?? '').split('-')
  return MESES[Number(numero) - 1] ? `${MESES[Number(numero) - 1]} ${anio}` : mes
}

// '2026-04' -> 'abr 26' (ejes de gráficos)
export function mesCorto(mes) {
  const [anio, numero] = (mes ?? '').split('-')
  return MESES[Number(numero) - 1] ? `${MESES[Number(numero) - 1].slice(0, 3)} ${anio.slice(2)}` : mes
}

export function formatMetrica(valor, esMoneda) {
  return esMoneda ? formatCLP(valor) : NUMERO.format(valor)
}
