import { useRef, useState } from 'react'
import { Download, FileBarChart2, Maximize2, Minimize2, MousePointerClick, Pencil, TableProperties, X } from 'lucide-react'
import { GraficoPrincipal } from './DashboardPanel.jsx'
import ReporteBD from './ReporteBD.jsx'
import { descargarReporte } from '../lib/api.js'
import './DashboardPanel.css'
import './ReporteGraficos.css'

function TituloEditable({ titulo, onGuardar }) {
  const [texto, setTexto] = useState(null)
  const cancelado = useRef(false)

  function guardar() {
    if (!cancelado.current && texto?.trim()) onGuardar(texto.trim())
    cancelado.current = false
    setTexto(null)
  }

  if (texto === null) {
    return (
      <h2>
        <FileBarChart2 size={17} strokeWidth={2.4} /> {titulo}
        <button type="button" className="reporte-renombrar" title="Cambiar nombre del dashboard" aria-label="Cambiar nombre del dashboard" onClick={() => setTexto(titulo)}>
          <Pencil size={13} />
        </button>
      </h2>
    )
  }
  return (
    <form onSubmit={(e) => { e.preventDefault(); guardar() }}>
      <input
        className="reporte-titulo-input"
        aria-label="Nombre del dashboard"
        placeholder="Nombre del dashboard"
        maxLength={100}
        autoFocus
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={guardar}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            cancelado.current = true
            e.currentTarget.blur()
          }
        }}
      />
    </form>
  )
}

const ALTO_EN_GRILLA = 340
const ALTO_AMPLIADO = 460

function TarjetaGrafico({ reporte, activo, onSeleccionar, onQuitar }) {
  const [ampliado, setAmpliado] = useState(false)
  const { interpretacion: i, resultado: r } = reporte
  const sinAgrupar = i.agruparPor === 'ninguno' || r.serie.length === 0
  const esMapa = i.visualizacion === 'mapa' && !sinAgrupar
  // Las barras de categorías se leen mejor de mayor a menor; los meses mantienen su orden
  const serie = i.visualizacion === 'barras' && i.agruparPor !== 'mes'
    ? [...r.serie].sort((a, b) => b.valor - a.valor)
    : r.serie
  const chips = [
    ...i.filtros.map((f) => f.valor),
    ...(i.desde || i.hasta ? [`${i.desde ?? '…'} a ${i.hasta ?? '…'}`] : []),
  ]
  return (
    <article className={`chart-card reporte-grafico ${activo ? 'reporte-grafico-activo' : ''} ${ampliado ? 'reporte-grafico-ampliado' : ''} ${esMapa ? 'reporte-grafico-mapa' : ''}`}>
      <header className="reporte-grafico-cabecera">
        <div>
          <span className="reporte-grafico-area">{i.dominio}</span>
          <h3 title={reporte.pregunta}>{reporte.pregunta}</h3>
          <p>{i.metricaEtiqueta}{sinAgrupar ? '' : ` por ${i.dimensionEtiqueta.toLowerCase()}`}{chips.length > 0 ? ` · ${chips.join(' · ')}` : ''}</p>
        </div>
        <div className="reporte-grafico-acciones">
          {!esMapa && (
            <button type="button" title={ampliado ? 'Reducir' : 'Ampliar a todo el ancho'} aria-label={ampliado ? 'Reducir gráfico' : 'Ampliar gráfico'} onClick={() => setAmpliado((v) => !v)}>
              {ampliado ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          )}
          <button type="button" title="Ver datos y filtrar este gráfico" aria-label="Ver datos y filtrar este gráfico" aria-pressed={activo} onClick={() => onSeleccionar(reporte)}>
            <TableProperties size={14} />
          </button>
          <button type="button" title="Quitar del reporte" aria-label="Quitar gráfico del reporte" onClick={() => onQuitar(reporte)}>
            <X size={15} />
          </button>
        </div>
      </header>
      {r.cantidad === 0
        ? <p className="chart-empty">Sin registros con estos filtros.</p>
        : (
          <GraficoPrincipal
            visualizacion={sinAgrupar ? 'kpi' : i.visualizacion}
            serie={serie}
            total={r.total}
            esMoneda={i.moneda}
            cantidad={r.cantidad}
            unidad="registros"
            compacto={!ampliado}
            altura={ampliado ? ALTO_AMPLIADO : ALTO_EN_GRILLA}
          />
        )}
    </article>
  )
}

// Un reporte es un chat: arriba los filtros, luego todos sus gráficos y al final
// los datos y el listado del gráfico seleccionado.
export default function ReporteGraficos({
  titulo, reportes, activo, filtros, actualizando, onSeleccionar, onQuitar, onRenombrar, onSesionExpirada,
}) {
  const [exportando, setExportando] = useState({ formato: null, error: '' })
  const seleccionado = activo?.esVistaArea ? activo : reportes.find((r) => r.id === activo?.id) ?? reportes.at(-1)

  async function exportar(formato) {
    setExportando({ formato, error: '' })
    try {
      await descargarReporte(formato, titulo.slice(0, 200), reportes.map((r) => ({ titulo: r.pregunta.slice(0, 200), plan: r.plan })))
      setExportando({ formato: null, error: '' })
    } catch (err) {
      if (err.estado === 401) {
        onSesionExpirada?.()
        return
      }
      setExportando({ formato: null, error: err.message || 'No se pudo generar el archivo.' })
    }
  }

  return (
    <div className="reporte-vista">
      {filtros}

      <div className="reporte-barra">
        <div>
          <TituloEditable titulo={titulo} onGuardar={onRenombrar} />
          <p>{reportes.length} {reportes.length === 1 ? 'gráfico' : 'gráficos'} · pide otro en el chat para agregarlo</p>
        </div>
        <div className="reporte-exportar">
          <div className="reporte-exportar-botones">
            <button type="button" className="btn-powerbi" onClick={() => exportar('html')} disabled={Boolean(exportando.formato)}>
              <MousePointerClick size={15} /> {exportando.formato === 'html' ? 'Generando…' : 'Descargar HTML interactivo'}
            </button>
            <button type="button" className="btn-powerbi btn-exportar-secundario" onClick={() => exportar('powerbi')} disabled={Boolean(exportando.formato)}>
              <Download size={15} /> {exportando.formato === 'powerbi' ? 'Generando…' : 'Exportar a Power BI'}
            </button>
          </div>
          {exportando.error && <p className="filters-error" role="alert">{exportando.error}</p>}
        </div>
      </div>

      <div className="reporte-grilla">
        {reportes.map((r) => (
          <TarjetaGrafico
            key={r.id}
            reporte={r}
            activo={r.id === seleccionado.id}
            onSeleccionar={onSeleccionar}
            onQuitar={onQuitar}
          />
        ))}
      </div>

      <ReporteBD reporte={seleccionado} actualizando={actualizando} mostrarGrafico={false} />
    </div>
  )
}
