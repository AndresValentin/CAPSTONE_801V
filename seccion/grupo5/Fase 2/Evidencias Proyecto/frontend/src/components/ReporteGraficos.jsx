import { useRef, useState } from 'react'
import { FileBarChart2, Lightbulb, Maximize2, Minimize2, MousePointerClick, Pencil, Save, TableProperties, X } from 'lucide-react'
import { GraficoPrincipal } from './DashboardPanel.jsx'
import ModalGuardarDashboard from './ModalGuardarDashboard.jsx'
import ReporteBD from './ReporteBD.jsx'
import ResumenAnalisis from './ResumenAnalisis.jsx'
import TextoEditable from './TextoEditable.jsx'
import { descargarReporte } from '../lib/api.js'
import { comparacionActiva } from '../lib/analisis.js'
import { tituloAutomatico, tituloGrafico } from '../lib/graficos.js'
import { lecturaGrafico } from '../lib/lectura.js'
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

// También la usa VistaDashboard (dashboards guardados). `controles` agrega botones
// propios a la cabecera; sin onSeleccionar, onQuitar u onRenombrar esas acciones no se muestran.
export function TarjetaGrafico({ reporte, activo = false, onSeleccionar, onQuitar, onRenombrar, controles = null }) {
  const [ampliado, setAmpliado] = useState(false)
  const { interpretacion: i, resultado: r } = reporte
  const sinAgrupar = i.agruparPor === 'ninguno' || r.serie.length === 0
  const esMapa = i.visualizacion === 'mapa' && !sinAgrupar
  // Las barras de categorías se leen mejor de mayor a menor; los meses mantienen su orden
  const serie = i.visualizacion === 'barras' && i.agruparPor !== 'mes'
    ? [...r.serie].sort((a, b) => b.valor - a.valor)
    : r.serie
  const titulo = tituloGrafico(reporte)
  // Bajo el título: qué mide (si el título es otro) y los filtros y el período aplicados
  const descripcion = tituloAutomatico(i)
  const subtitulo = [
    ...(descripcion !== titulo ? [descripcion] : []),
    ...i.filtros.map((f) => f.valor),
    ...(i.desde || i.hasta ? [i.desde === i.hasta ? i.desde : `${i.desde ?? '…'} a ${i.hasta ?? '…'}`] : []),
  ].join(' · ')
  const comparacion = comparacionActiva(r)
  const lectura = lecturaGrafico(reporte)
  return (
    <article className={`chart-card reporte-grafico ${activo ? 'reporte-grafico-activo' : ''} ${ampliado ? 'reporte-grafico-ampliado' : ''} ${esMapa ? 'reporte-grafico-mapa' : ''}`}>
      <header className="reporte-grafico-cabecera">
        <div>
          <span className="reporte-grafico-area">{i.dominio}</span>
          <TextoEditable
            texto={titulo}
            etiqueta="título del gráfico"
            onGuardar={onRenombrar && ((nuevo) => onRenombrar(reporte, nuevo))}
            ayuda={reporte.pregunta && reporte.pregunta !== titulo ? `Pedido como: «${reporte.pregunta}»` : titulo}
          />
          {subtitulo && <p>{subtitulo}</p>}
        </div>
        <div className="reporte-grafico-acciones">
          {controles}
          {!esMapa && (
            <button type="button" title={ampliado ? 'Reducir' : 'Ampliar a todo el ancho'} aria-label={ampliado ? 'Reducir gráfico' : 'Ampliar gráfico'} onClick={() => setAmpliado((v) => !v)}>
              {ampliado ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          )}
          {onSeleccionar && (
            <button type="button" title="Ver datos, filtrar y comparar este gráfico" aria-label="Ver datos, filtrar y comparar este gráfico" aria-pressed={activo} onClick={() => onSeleccionar(reporte)}>
              <TableProperties size={14} />
            </button>
          )}
          {onQuitar && (
            <button type="button" title="Quitar del reporte" aria-label="Quitar gráfico del reporte" onClick={() => onQuitar(reporte)}>
              <X size={15} />
            </button>
          )}
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
            comparacion={comparacion}
            proyeccion={r.proyeccion?.omitida ? null : r.proyeccion}
          />
        )}
      {(reporte.lectura || lectura) && (
        <div className="reporte-lectura">
          <Lightbulb size={13} />
          <p>
            {reporte.lectura && <span className="reporte-lectura-pregunta">{reporte.lectura}</span>}
            {lectura}
          </p>
        </div>
      )}
      <ResumenAnalisis resultado={r} esMoneda={i.moneda} soloAvisos={sinAgrupar} />
    </article>
  )
}

// Un reporte es un chat: arriba los filtros, luego todos sus gráficos y al final
// los datos y el listado del gráfico seleccionado.
export default function ReporteGraficos({
  titulo, reportes, activo, filtros, actualizando, onSeleccionar, onQuitar, onRenombrar, onRenombrarGrafico, onSesionExpirada,
}) {
  const [exportando, setExportando] = useState({ formato: null, error: '' })
  const [guardando, setGuardando] = useState(false)
  const seleccionado = activo?.esVistaArea ? activo : reportes.find((r) => r.id === activo?.id) ?? reportes.at(-1)
  // Lo que se guarda o exporta lleva el título que se ve en pantalla
  const graficosConTitulo = () => reportes.map((r) => ({ titulo: tituloGrafico(r).slice(0, 200), plan: r.plan }))

  async function exportar(formato) {
    setExportando({ formato, error: '' })
    try {
      const { omitidos } = await descargarReporte(formato, titulo.slice(0, 200), graficosConTitulo())
      setExportando({
        formato: null,
        error: omitidos
          ? `Se descargó sin ${omitidos === 1 ? '1 gráfico que ya no calza' : `${omitidos} gráficos que ya no calzan`} con el catálogo actual. Pídelo de nuevo en el chat para incluirlo.`
          : '',
      })
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
            <button type="button" className="btn-powerbi" onClick={() => setGuardando(true)}>
              <Save size={15} /> Guardar como dashboard
            </button>
            <button type="button" className="btn-powerbi btn-exportar-secundario" onClick={() => exportar('html')} disabled={Boolean(exportando.formato)}>
              <MousePointerClick size={15} /> {exportando.formato === 'html' ? 'Generando…' : 'Descargar HTML interactivo'}
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
            onRenombrar={onRenombrarGrafico}
          />
        ))}
      </div>

      <ReporteBD reporte={seleccionado} actualizando={actualizando} mostrarGrafico={false} />

      {guardando && (
        <ModalGuardarDashboard
          nombreInicial={titulo}
          graficos={graficosConTitulo()}
          onCerrar={() => setGuardando(false)}
          onSesionExpirada={onSesionExpirada}
        />
      )}
    </div>
  )
}
