import { useEffect, useRef, useState } from 'react'
import {
  Bot, SendHorizontal, ShieldAlert, Paperclip, FileSpreadsheet, LayoutDashboard,
  SquarePen, AlertTriangle, CheckCircle2, Sparkles,
} from 'lucide-react'
import { EXTENSIONES_ACEPTADAS } from '../lib/importacion.js'
import { METRICAS, DIMENSIONES, VISUALIZACIONES, completarReporte } from '../data/mockData.js'
import './ChatCopilot.css'

const SUGERENCIAS = [
  'Genera un reporte del monto pagado por región en barras',
  'Genera un reporte de la cantidad de siniestros por mes en Automotriz',
  'Genera un reporte de siniestros por estado en torta',
  'Genera un reporte del monto promedio en Valparaíso como KPI',
]

const GUIA = [
  ['Qué medir', 'monto pagado, cantidad de siniestros o monto promedio'],
  ['Filtros', 'producto, región, estado o período (AAAA-MM)'],
  ['Cómo verlo', 'barras, líneas, torta, KPI o tabla'],
]

function detalleReporte(interpretacion) {
  // Los reportes del backend ya traen sus etiquetas; los del modo demo se completan aquí
  if (interpretacion.metricaEtiqueta) {
    return [
      ['Dominio', interpretacion.dominio],
      ['Métrica', interpretacion.metricaEtiqueta],
      ['Agrupado por', interpretacion.dimensionEtiqueta],
      ['Visualización', VISUALIZACIONES[interpretacion.visualizacion] ?? interpretacion.visualizacion],
    ]
  }
  const r = completarReporte(interpretacion)
  return [
    ['Métrica', METRICAS[r.metrica].etiqueta],
    ['Agrupado por', DIMENSIONES[r.agruparPor]],
    ['Visualización', VISUALIZACIONES[r.visualizacion]],
    ['Catálogo', interpretacion.catalogoVersion],
  ]
}

function MensajeAsistente({ m, reporteActivoId, onVerReporte, onResponder }) {
  return (
    <>
      <p className="chat-text">{m.texto}</p>

      {m.tipo === 'aclaracion' && (
        <div className="quick-replies">
          {SUGERENCIAS.slice(0, 3).map((s) => (
            <button key={s} type="button" className="suggestion-chip" onClick={() => onResponder(s)}>{s}</button>
          ))}
        </div>
      )}

      {m.tipo === 'validado' && (
        <>
          <div className="interpretation-card">
            {detalleReporte(m.interpretacion).map(([k, v]) => (
              <div key={k} className="interpretation-row"><span>{k}</span><strong>{v}</strong></div>
            ))}
          </div>
          <button
            type="button"
            className={`report-link ${reporteActivoId === m.id ? 'report-link-active' : ''}`}
            onClick={() => onVerReporte(m)}
          >
            <LayoutDashboard size={12} />
            {reporteActivoId === m.id ? 'Mostrando en el dashboard' : 'Ver reporte en el dashboard'}
          </button>
        </>
      )}

      {m.tipo === 'rechazo' && (
        <span className="reject-tag"><ShieldAlert size={12} /> No se ejecutó ninguna consulta</span>
      )}

      {m.tipo === 'importacion' && (
        <div className={`import-result ${m.resumen.rechazados ? 'import-result-warn' : ''}`}>
          <span className="import-result-head">
            {m.resumen.rechazados ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} />}
            {m.resumen.importados} importados · {m.resumen.rechazados} rechazados
          </span>
          {m.resumen.detalleErrores.map((err) => (
            <span key={err.fila} className="import-result-error">Fila {err.fila}: {err.errores.join(', ')}</span>
          ))}
        </div>
      )}
    </>
  )
}

export default function ChatCopilot({
  conversacion, pensando, reporteActivoId, onEnviar, onAdjuntar, onVerReporte, onNuevoChat,
}) {
  const [texto, setTexto] = useState('')
  const [arrastrando, setArrastrando] = useState(false)
  const listRef = useRef(null)
  const fileRef = useRef(null)
  const { mensajes } = conversacion
  const vacio = mensajes.length === 0 && !pensando

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [mensajes.length, pensando, conversacion.id])

  function enviar(contenido) {
    const limpio = contenido.trim()
    if (!limpio || pensando) return
    setTexto('')
    onEnviar(limpio)
  }

  function adjuntar(file) {
    if (!file || pensando) return
    // El error ya queda registrado como mensaje en el chat
    onAdjuntar(file).catch(() => {})
  }

  function handleDrop(e) {
    e.preventDefault()
    setArrastrando(false)
    adjuntar(e.dataTransfer.files[0])
  }

  return (
    <section
      className={`chat-copilot ${arrastrando ? 'chat-dragging' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setArrastrando(true) }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setArrastrando(false) }}
      onDrop={handleDrop}
    >
      <div className="panel-title-row">
        <h2><Bot size={16} strokeWidth={2.4} /> BI Copilot</h2>
        <button type="button" className="icon-btn" title="Nuevo reporte" onClick={onNuevoChat}>
          <SquarePen size={15} />
        </button>
      </div>
      <p className="panel-subtitle chat-title">{conversacion.titulo}</p>

      <div className="chat-messages" ref={listRef}>
        {vacio && (
          <div className="chat-welcome">
            <span className="chat-welcome-icon"><Sparkles size={20} /></span>
            <h3>¿Qué reporte necesitas?</h3>
            <p>Pídeme que genere un reporte y lo armo en la plantilla. Para hacerlo bien, cuéntame:</p>
            <ul className="chat-guide">
              {GUIA.map(([titulo, detalle]) => (
                <li key={titulo}><strong>{titulo}</strong><span>{detalle}</span></li>
              ))}
            </ul>
            <div className="chat-suggestions">
              {SUGERENCIAS.map((s) => (
                <button key={s} type="button" className="suggestion-chip" onClick={() => enviar(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {mensajes.map((m) => (
          <div key={m.id} className={`chat-bubble chat-${m.rol} ${m.tipo === 'error' ? 'chat-error' : ''}`}>
            {m.rol === 'usuario' && m.tipo === 'archivo' && (
              <span className="file-chip"><FileSpreadsheet size={14} /> {m.texto}</span>
            )}
            {m.rol === 'usuario' && m.tipo !== 'archivo' && <p>{m.texto}</p>}
            {m.rol === 'asistente' && (
              <MensajeAsistente m={m} reporteActivoId={reporteActivoId} onVerReporte={onVerReporte} onResponder={enviar} />
            )}
          </div>
        ))}

        {pensando && (
          <div className="chat-bubble chat-asistente chat-thinking">
            <span /><span /><span />
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); enviar(texto) }}>
        <input
          ref={fileRef}
          type="file"
          accept={EXTENSIONES_ACEPTADAS}
          className="chat-file-input"
          onChange={(e) => { adjuntar(e.target.files[0]); e.target.value = '' }}
        />
        <button
          type="button"
          className="btn-attach"
          title="Adjuntar Excel o CSV"
          onClick={() => fileRef.current?.click()}
          disabled={pensando}
        >
          <Paperclip size={16} />
        </button>
        <input
          type="text"
          placeholder="Ej: genera un reporte del monto pagado por región"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
        <button type="submit" className="btn-primary btn-send" disabled={pensando}>
          <SendHorizontal size={15} />
        </button>
      </form>

      {arrastrando && (
        <div className="chat-drop-overlay">
          <FileSpreadsheet size={28} />
          Suelta tu Excel o CSV para importarlo
        </div>
      )}
    </section>
  )
}
