import { ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { formatCLP, formatCLPCorto } from '../lib/formato.js'
import './MLPanel.css'

// Recibe la proyección ya calculada (lib/regression.js → proyectarMonto)
export default function MLPanel({ analisis }) {
  if (!analisis) {
    return <p className="ml-empty">Se necesitan al menos 2 meses de datos con los filtros actuales para proyectar.</p>
  }

  const sube = analisis.modelo.pendiente >= 0

  return (
    <div className="ml-panel">
      <ResponsiveContainer width="100%" height={100}>
        <ComposedChart data={analisis.chartData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
          <XAxis dataKey="fecha" tick={{ fontSize: 9 }} interval="preserveStartEnd" tickLine={false} />
          <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `${Math.round(v / 1e6)}M`} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => (v == null ? '—' : formatCLP(v))} />
          <Line type="monotone" dataKey="real" name="Real" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 2 }} />
          <Line type="monotone" dataKey="proyectado" name="Proyectado" stroke="var(--color-accent)" strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2 }} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="ml-forecast">
        {sube ? <TrendingUp size={14} className="ml-trend-up" /> : <TrendingDown size={14} className="ml-trend-down" />}
        <div>
          <span className="ml-forecast-label">Proyección {analisis.proximoMes}</span>
          <strong className="ml-forecast-value">{formatCLP(analisis.proyeccion)}</strong>
        </div>
      </div>

      <div className="ml-stats">
        <span>R² {(analisis.modelo.r2 * 100).toFixed(0)}%</span>
        <span>{sube ? '+' : ''}{formatCLPCorto(analisis.modelo.pendiente)}/mes</span>
      </div>
      <p className="ml-disclaimer">Regresión lineal sobre el monto pagado mensual de los datos filtrados.</p>
    </div>
  )
}
