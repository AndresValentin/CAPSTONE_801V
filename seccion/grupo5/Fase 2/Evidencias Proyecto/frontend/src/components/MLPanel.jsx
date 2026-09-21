import { useMemo } from 'react'
import { ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts'
import { BrainCircuit, TrendingUp, TrendingDown } from 'lucide-react'
import { resumenPorMes } from '../data/mockData.js'
import { regresionLineal, siguienteMes } from '../lib/regression.js'
import './MLPanel.css'

function formatCLP(valor) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(valor)
}

export default function MLPanel({ datos }) {
  const analisis = useMemo(() => {
    const serie = resumenPorMes(datos)
    if (serie.length < 2) return null

    const puntos = serie.map((s, i) => ({ x: i, y: s.monto }))
    const modelo = regresionLineal(puntos)
    if (!modelo) return null

    const proximoMes = siguienteMes(serie[serie.length - 1].fecha)
    const proyeccion = Math.max(0, Math.round(modelo.predecir(serie.length)))

    const chartData = serie.map((s) => ({ fecha: s.fecha, real: s.monto, proyectado: null }))
    chartData.push({ fecha: proximoMes, real: null, proyectado: proyeccion })
    // Conecta la última barra real con la proyección
    chartData[chartData.length - 2].proyectado = chartData[chartData.length - 2].real

    return { modelo, proximoMes, proyeccion, chartData }
  }, [datos])

  return (
    <div>
      <div className="module-title">
        <span className="module-title-icon"><BrainCircuit size={13} /></span>
        Machine Learning
      </div>
      <p className="module-hint">Proyección de monto pagado por regresión lineal</p>

      {!analisis && (
        <p className="ml-empty">Se necesitan al menos 2 meses de datos con los filtros actuales para proyectar.</p>
      )}

      {analisis && (
        <>
          <ResponsiveContainer width="100%" height={110}>
            <ComposedChart data={analisis.chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="fecha" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `${Math.round(v / 1e6)}M`} />
              <Tooltip formatter={(v) => (v == null ? '—' : formatCLP(v))} />
              <Line type="monotone" dataKey="real" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 2 }} />
              <Line type="monotone" dataKey="proyectado" stroke="var(--color-accent)" strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>

          <div className="ml-forecast">
            {analisis.modelo.pendiente >= 0
              ? <TrendingUp size={14} className="ml-trend-up" />
              : <TrendingDown size={14} className="ml-trend-down" />}
            <div>
              <span className="ml-forecast-label">Proyección {analisis.proximoMes}</span>
              <strong className="ml-forecast-value">{formatCLP(analisis.proyeccion)}</strong>
            </div>
          </div>

          <div className="ml-stats">
            <span>R² {(analisis.modelo.r2 * 100).toFixed(0)}%</span>
            <span>Tendencia {analisis.modelo.pendiente >= 0 ? '+' : ''}{formatCLP(analisis.modelo.pendiente)}/mes</span>
          </div>
          <p className="ml-disclaimer">Estimación estadística en el navegador, no un modelo entrenado.</p>
        </>
      )}
    </div>
  )
}
