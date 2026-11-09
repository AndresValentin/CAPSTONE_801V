import { SlidersHorizontal, Layers, Filter, CalendarRange, RotateCcw } from 'lucide-react'
import './FiltersPanel.css'

// Barra de filtros del modo backend. Los campos y sus valores vienen de
// GET /api/catalogo, así que cambian según el dominio y los permisos del usuario.
// Los filtros recalculan el gráfico o el área en pantalla; si aún no hay gráficos,
// también se envían con la próxima pregunta. Cambiar el área muestra los datos de esa área.
export default function FiltrosBD({ catalogo, panel, onCambiar, onCambiarArea, resultados, actualizando, error, titulo = 'Filtros' }) {
  const dominios = catalogo?.dominios ?? []
  const dominio = dominios.find((d) => d.codigo === panel.dominio) ?? dominios[0]
  if (!dominio) return null

  function cambiar(cambios) {
    onCambiar({ ...panel, dominio: dominio.codigo, ...cambios })
  }

  function cambiarFiltro(campo, valor) {
    const filtros = { ...panel.filtros }
    if (valor) filtros[campo] = valor
    else delete filtros[campo]
    cambiar({ filtros })
  }

  const hayFiltros = Object.keys(panel.filtros).length > 0 || panel.desde || panel.hasta

  return (
    <div className="filters-bar filters-bar-bd">
      <div className="filtros-cabecera">
        <div className="filters-bar-title">
          <SlidersHorizontal size={15} strokeWidth={2.4} />
          <span>{titulo}</span>
        </div>
        <div className="filtros-acciones">
          <button className="link-btn" onClick={() => cambiar({ filtros: {}, desde: '', hasta: '' })} disabled={!hayFiltros}>
            <RotateCcw size={13} /> Limpiar
          </button>
          {resultados !== undefined && (
            <div className={`filter-result-chip ${actualizando ? 'filter-result-chip-cargando' : ''}`}>
              {actualizando
                ? 'Actualizando…'
                : <><strong>{resultados.toLocaleString('es-CL')}</strong> {resultados === 1 ? 'registro' : 'registros'}</>}
            </div>
          )}
        </div>
      </div>

      <div className="filtros-campos">
      {dominios.length > 1 && (
        <div className="filter-field">
          <label><Layers size={13} /> Área</label>
          <select
            value={dominio.codigo}
            onChange={(e) => onCambiarArea(e.target.value)}
          >
            {dominios.map((d) => <option key={d.codigo} value={d.codigo}>{d.nombre}</option>)}
          </select>
        </div>
      )}

      {dominio.filtros.map((f) => (
        <div key={f.campo} className="filter-field">
          <label><Filter size={13} /> {f.etiqueta}</label>
          <select value={panel.filtros[f.campo] ?? ''} onChange={(e) => cambiarFiltro(f.campo, e.target.value)}>
            <option value="">Todos</option>
            {f.valores.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      ))}

      {dominio.fecha && (
        <div className="filter-field filter-field-dates">
          <label title={dominio.fecha.etiqueta}><CalendarRange size={13} /> Rango</label>
          <div className="date-range">
            <input
              type="month"
              min={dominio.fecha.desde}
              max={panel.hasta || dominio.fecha.hasta}
              value={panel.desde}
              onChange={(e) => cambiar({ desde: e.target.value })}
            />
            <span className="date-sep">–</span>
            <input
              type="month"
              min={panel.desde || dominio.fecha.desde}
              max={dominio.fecha.hasta}
              value={panel.hasta}
              onChange={(e) => cambiar({ hasta: e.target.value })}
            />
          </div>
        </div>
      )}

      </div>

      {error &&<p className="filters-error" role="alert">{error}</p>}
    </div>
  )
}
