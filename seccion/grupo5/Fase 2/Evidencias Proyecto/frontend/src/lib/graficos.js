// Título que se arma solo a partir de lo que muestra el gráfico ("Monto pagado por región"),
// en vez de la pregunta tal como se escribió en el chat. Los filtros y el período van aparte.
export function tituloAutomatico(interpretacion) {
  const { metricaEtiqueta = '', agruparPor, dimensionEtiqueta } = interpretacion
  return agruparPor && agruparPor !== 'ninguno' && dimensionEtiqueta
    ? `${metricaEtiqueta} por ${dimensionEtiqueta.toLowerCase()}`
    : metricaEtiqueta
}

// Título que se muestra, se guarda en los dashboards y se exporta: el que puso el usuario
// o, si no puso ninguno (o lo dejó vacío), el automático
export function tituloGrafico(reporte) {
  return reporte.titulo?.trim()
    || (reporte.interpretacion?.metricaEtiqueta ? tituloAutomatico(reporte.interpretacion) : reporte.pregunta)
    || 'Gráfico'
}

// Tooltip de Recharts con los colores del tema activo
export const ESTILO_TOOLTIP = {
  contentStyle: {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 8,
    color: 'var(--color-text)',
  },
  labelStyle: { color: 'var(--color-text)' },
  itemStyle: { color: 'var(--color-text)' },
}
