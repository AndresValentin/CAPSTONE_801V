// Regresión lineal simple (mínimos cuadrados) para proyectar una serie mensual.
// Es una heurística estadística en el navegador, no un modelo de ML entrenado.

export function regresionLineal(puntos) {
  const n = puntos.length
  if (n < 2) return null

  let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0
  puntos.forEach(({ x, y }) => {
    sumX += x
    sumY += y
    sumXY += x * y
    sumXX += x * x
  })

  const denominador = n * sumXX - sumX * sumX
  if (denominador === 0) return null

  const pendiente = (n * sumXY - sumX * sumY) / denominador
  const intercepto = (sumY - pendiente * sumX) / n
  const predecir = (x) => pendiente * x + intercepto

  const mediaY = sumY / n
  let ssRes = 0, ssTot = 0
  puntos.forEach(({ x, y }) => {
    ssRes += (y - predecir(x)) ** 2
    ssTot += (y - mediaY) ** 2
  })
  const r2 = ssTot === 0 ? 1 : 1 - ssRes / ssTot

  return { pendiente, intercepto, r2, predecir }
}

export function siguienteMes(mesTexto) {
  const [anio, mes] = mesTexto.split('-').map(Number)
  const fecha = new Date(anio, mes - 1 + 1, 1)
  const yyyy = fecha.getFullYear()
  const mm = String(fecha.getMonth() + 1).padStart(2, '0')
  return `${yyyy}-${mm}`
}

function indiceMes(mesTexto) {
  const [anio, mes] = mesTexto.split('-').map(Number)
  return anio * 12 + mes
}

// Proyecta el monto del mes siguiente a partir de una serie mensual
// [{ fecha: 'AAAA-MM', monto }]. El eje x usa la distancia real entre meses,
// así un mes sin datos (por los filtros) no deforma la pendiente.
export function proyectarMonto(serie) {
  if (serie.length < 2) return null
  const inicio = indiceMes(serie[0].fecha)
  const modelo = regresionLineal(serie.map((s) => ({ x: indiceMes(s.fecha) - inicio, y: s.monto })))
  if (!modelo) return null

  const ultimo = serie[serie.length - 1].fecha
  const proximoMes = siguienteMes(ultimo)
  const proyeccion = Math.max(0, Math.round(modelo.predecir(indiceMes(proximoMes) - inicio)))

  const chartData = serie.map((s) => ({ fecha: s.fecha, real: s.monto, proyectado: null }))
  // Conecta el último punto real con la proyección
  chartData[chartData.length - 1].proyectado = chartData[chartData.length - 1].real
  chartData.push({ fecha: proximoMes, real: null, proyectado: proyeccion })

  return { modelo, proximoMes, proyeccion, chartData }
}
