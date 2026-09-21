import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, PieChart, Pie, Cell,
} from 'recharts'
import { LayoutDashboard, FileStack, CircleDollarSign, TrendingUp } from 'lucide-react'
import { resumenPorProducto, resumenPorMes, resumenPorEstado } from '../data/mockData.js'
import './DashboardPanel.css'

const COLORS = ['#1e2a5e', '#14b8a6', '#2563eb', '#d97706', '#7c3aed']

function formatCLP(valor) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(valor)
}

export default function DashboardPanel({ datos, filtros, solicitud }) {
  const porProducto = resumenPorProducto(datos)
  const porMes = resumenPorMes(datos)
  const porEstado = resumenPorEstado(datos)

  const montoTotal = datos.reduce((acc, s) => acc + s.monto, 0)
  const montoPromedio = datos.length ? montoTotal / datos.length : 0

  const filtrosActivos = Object.entries(filtros).filter(([, v]) => v && v !== 'Todos' && v !== 'Todas')

  return (
    <section className="dashboard-panel">
      <div className="panel-title-row">
        <div>
          <h2><LayoutDashboard size={16} strokeWidth={2.4} /> Dashboard generado por IA</h2>
          <p className="panel-subtitle">Resultado presentable según plantilla controlada (RF-06)</p>
        </div>
        {solicitud && (
          <span className={`badge badge-${solicitud.estado}`}>
            {solicitud.estado === 'validado' ? 'Solicitud validada' : 'Solicitud rechazada'}
          </span>
        )}
      </div>

      {filtrosActivos.length > 0 && (
        <div className="active-filters">
          {filtrosActivos.map(([k, v]) => (
            <span key={k} className="filter-chip">{k}: {v}</span>
          ))}
        </div>
      )}

      <div className="kpi-row">
        <div className="kpi-card">
          <span className="kpi-icon kpi-icon-blue"><FileStack size={16} /></span>
          <span className="kpi-label">Siniestros</span>
          <span className="kpi-value">{datos.length}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-icon kpi-icon-teal"><CircleDollarSign size={16} /></span>
          <span className="kpi-label">Monto pagado total</span>
          <span className="kpi-value">{formatCLP(montoTotal)}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-icon kpi-icon-amber"><TrendingUp size={16} /></span>
          <span className="kpi-label">Monto promedio</span>
          <span className="kpi-value">{formatCLP(montoPromedio)}</span>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <h3>Monto pagado por producto</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={porProducto}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="producto" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${Math.round(v / 1000000)}M`} />
              <Tooltip formatter={(v) => formatCLP(v)} />
              <Bar dataKey="monto" fill="#4f46e5" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Cantidad de siniestros por mes</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={porMes}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="fecha" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="cantidad" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Distribución por estado</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={porEstado} dataKey="cantidad" nameKey="estado" innerRadius={45} outerRadius={75}>
                {porEstado.map((entry, i) => (
                  <Cell key={entry.estado} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-card">
        <h3>Detalle ({datos.length} registros)</h3>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Siniestro</th>
                <th>Póliza</th>
                <th>Producto</th>
                <th>Región</th>
                <th>Estado</th>
                <th>Fecha</th>
                <th>Monto</th>
              </tr>
            </thead>
            <tbody>
              {datos.slice(0, 12).map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.poliza}</td>
                  <td>{s.producto}</td>
                  <td>{s.region}</td>
                  <td><span className={`status-pill status-${s.estado.replace(' ', '-')}`}>{s.estado}</span></td>
                  <td>{s.fecha}</td>
                  <td>{formatCLP(s.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
