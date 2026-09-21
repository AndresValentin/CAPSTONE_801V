import { useRef, useState } from 'react'
import { Bot, SendHorizontal, ShieldAlert } from 'lucide-react'
import { interpretarSolicitud } from '../lib/copilot.js'
import './ChatCopilot.css'

const SUGERENCIAS = [
  'Monto pagado total en Automotriz durante 2026-02',
  'Cantidad de siniestros en Valparaíso',
  'Muéstrame el correo de los clientes',
  'Elimina los registros de Hogar',
]

function mensajeInicial() {
  return [
    {
      id: 'm0',
      rol: 'asistente',
      texto: 'Hola, soy BI Copilot. Escribe una pregunta sobre el dominio de Siniestros y validaré la solicitud antes de generar el resultado.',
    },
  ]
}

export default function ChatCopilot({ onFiltrosSugeridos, onNuevaSolicitud }) {
  const [mensajes, setMensajes] = useState(mensajeInicial)
  const [texto, setTexto] = useState('')
  const listRef = useRef(null)

  function enviar(textoForzado) {
    const contenido = (textoForzado ?? texto).trim()
    if (!contenido) return

    const resultado = interpretarSolicitud(contenido)
    onNuevaSolicitud?.({
      id: crypto.randomUUID(),
      texto: contenido,
      fecha: new Date(),
      estado: resultado.estado,
      motivo: resultado.motivo,
      interpretacion: resultado.interpretacion,
    })

    const nuevoUsuario = { id: crypto.randomUUID(), rol: 'usuario', texto: contenido }
    let respuesta

    if (resultado.estado === 'rechazado') {
      respuesta = {
        id: crypto.randomUUID(),
        rol: 'asistente',
        tipo: 'rechazo',
        texto: resultado.motivo,
      }
    } else {
      const { interpretacion } = resultado
      onFiltrosSugeridos?.({
        producto: interpretacion.filtros.producto || 'Todos',
        region: interpretacion.filtros.region || 'Todas',
        estado: interpretacion.filtros.estado || 'Todos',
      })
      respuesta = {
        id: crypto.randomUUID(),
        rol: 'asistente',
        tipo: 'validado',
        texto: 'Solicitud validada contra el catálogo. Actualicé el dashboard con el resultado.',
        interpretacion,
      }
    }

    setMensajes((prev) => [...prev, nuevoUsuario, respuesta])
    setTexto('')
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  function handleSubmit(e) {
    e.preventDefault()
    enviar()
  }

  return (
    <section className="chat-copilot">
      <div className="panel-title-row">
        <h2><Bot size={16} strokeWidth={2.4} /> BI Copilot</h2>
        <span className="status-dot" title="Consultas de solo lectura" />
      </div>
      <p className="panel-subtitle">Lenguaje natural con validación previa a la ejecución</p>

      <div className="chat-messages" ref={listRef}>
        {mensajes.map((m) => (
          <div key={m.id} className={`chat-bubble chat-${m.rol}`}>
            <p>{m.texto}</p>
            {m.tipo === 'validado' && (
              <div className="interpretation-card">
                <div className="interpretation-row">
                  <span>Métrica</span>
                  <strong>{m.interpretacion.metrica}</strong>
                </div>
                <div className="interpretation-row">
                  <span>Salida</span>
                  <strong>{m.interpretacion.tipoSalida}</strong>
                </div>
                <div className="interpretation-row">
                  <span>Catálogo</span>
                  <strong>{m.interpretacion.catalogoVersion}</strong>
                </div>
              </div>
            )}
            {m.tipo === 'rechazo' && (
              <span className="reject-tag"><ShieldAlert size={12} /> No se ejecutó ninguna consulta</span>
            )}
          </div>
        ))}
      </div>

      <div className="chat-suggestions">
        {SUGERENCIAS.map((s) => (
          <button key={s} type="button" className="suggestion-chip" onClick={() => enviar(s)}>
            {s}
          </button>
        ))}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Ej: monto pagado total por región en marzo"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
        <button type="submit" className="btn-primary btn-send"><SendHorizontal size={15} /></button>
      </form>
    </section>
  )
}
