import { SlidersHorizontal, Package, MapPin, CircleCheck, CalendarRange, RotateCcw } from 'lucide-react'
import { productos, regiones, estados } from '../data/mockData.js'
import './FiltersPanel.css'

export default function FiltersPanel({ filtros, setFiltros, resultados }) {
  function update(campo, valor) {
    setFiltros((prev) => ({ ...prev, [campo]: valor }))
  }

  function limpiar() {
    setFiltros({ producto: 'Todos', region: 'Todas', estado: 'Todos', desde: '', hasta: '' })
  }

  return (
    <div className="filters-bar">
      <div className="filters-bar-title">
        <SlidersHorizontal size={15} strokeWidth={2.4} />
        <span>Filtros</span>
      </div>

      <div className="filter-field">
        <label><Package size={13} /> Producto</label>
        <select value={filtros.producto} onChange={(e) => update('producto', e.target.value)}>
          <option>Todos</option>
          {productos.map((p) => <option key={p}>{p}</option>)}
        </select>
      </div>

      <div className="filter-field">
        <label><MapPin size={13} /> Región</label>
        <select value={filtros.region} onChange={(e) => update('region', e.target.value)}>
          <option>Todas</option>
          {regiones.map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      <div className="filter-field">
        <label><CircleCheck size={13} /> Estado</label>
        <select value={filtros.estado} onChange={(e) => update('estado', e.target.value)}>
          <option>Todos</option>
          {estados.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      <div className="filter-field filter-field-dates">
        <label><CalendarRange size={13} /> Rango</label>
        <div className="date-range">
          <input type="month" value={filtros.desde} onChange={(e) => update('desde', e.target.value)} />
          <span className="date-sep">–</span>
          <input type="month" value={filtros.hasta} onChange={(e) => update('hasta', e.target.value)} />
        </div>
      </div>

      <button className="link-btn" onClick={limpiar}>
        <RotateCcw size={13} /> Limpiar
      </button>

      <div className="filter-result-chip">
        <strong>{resultados}</strong> registros
      </div>
    </div>
  )
}
