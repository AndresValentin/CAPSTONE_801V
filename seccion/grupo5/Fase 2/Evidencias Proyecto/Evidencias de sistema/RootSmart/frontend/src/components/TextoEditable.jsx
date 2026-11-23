import { useRef, useState } from 'react'
import { Pencil } from 'lucide-react'

// Texto que se edita en el mismo lugar, como el título de un visual en Power BI: con el
// lápiz o con doble clic. Enter guarda, Escape cancela y dejarlo vacío vuelve al automático.
// Sin `onGuardar` es solo texto (por ejemplo, para un lector de un dashboard compartido).
export default function TextoEditable({ texto, etiqueta, onGuardar, como: Etiqueta = 'h3', ayuda, maxLength = 120 }) {
  const [borrador, setBorrador] = useState(null)
  const cancelado = useRef(false)

  function terminar() {
    if (!cancelado.current && borrador !== null && borrador.trim() !== texto) onGuardar(borrador.trim())
    cancelado.current = false
    setBorrador(null)
  }

  if (!onGuardar) return <Etiqueta title={ayuda ?? texto}>{texto}</Etiqueta>

  if (borrador === null) {
    return (
      <Etiqueta className="texto-editable" title={ayuda ?? texto} onDoubleClick={() => setBorrador(texto)}>
        <span className="texto-editable-valor">{texto}</span>
        <button
          type="button"
          className="texto-editable-lapiz"
          title={`Cambiar ${etiqueta}`}
          aria-label={`Cambiar ${etiqueta}`}
          onClick={() => setBorrador(texto)}
        >
          <Pencil size={12} />
        </button>
      </Etiqueta>
    )
  }

  return (
    <input
      className="texto-editable-input"
      aria-label={etiqueta}
      placeholder="Vacío = título automático"
      maxLength={maxLength}
      autoFocus
      value={borrador}
      onFocus={(e) => e.currentTarget.select()}
      onChange={(e) => setBorrador(e.target.value)}
      onBlur={terminar}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur()
        if (e.key === 'Escape') {
          cancelado.current = true
          e.currentTarget.blur()
        }
      }}
    />
  )
}
