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

export function formatMetrica(valor, esMoneda) {
  return esMoneda ? formatCLP(valor) : NUMERO.format(valor)
}
