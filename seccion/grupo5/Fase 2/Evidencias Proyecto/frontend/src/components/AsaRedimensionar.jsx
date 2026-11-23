import { useRef } from 'react'

const PASO_TECLADO = 16

// Borde que se arrastra para cambiar el ancho de un panel (historial o chat).
// Mientras se arrastra, el ancho se aplica directo a la variable CSS del contenedor,
// sin re-renderizar la página; al soltar se guarda con `onCambiar`.
// `invertido`: el panel está a la derecha, así que arrastrar a la izquierda lo agranda.
// También funciona con teclado (flechas, Inicio y Fin) y doble clic vuelve al ancho original.
export default function AsaRedimensionar({
  etiqueta, contenedor, variable, ancho, min, max, porDefecto, invertido = false, onCambiar, className = '',
}) {
  const arrastre = useRef(null)

  function limitar(valor) {
    return Math.round(Math.min(max(), Math.max(min, valor)))
  }

  function aplicar(valor) {
    contenedor.current?.style.setProperty(variable, `${valor}px`)
  }

  function terminar() {
    if (!arrastre.current) return
    const { inicio, ultimo } = arrastre.current
    arrastre.current = null
    document.body.classList.remove('redimensionando')
    if (ultimo !== inicio) onCambiar(ultimo)
  }

  return (
    <div
      className={`asa-redimensionar ${className}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={etiqueta}
      aria-valuenow={ancho}
      aria-valuemin={min}
      aria-valuemax={max()}
      tabIndex={0}
      title={`${etiqueta}: arrastra para cambiarlo · doble clic para volver al original`}
      onPointerDown={(e) => {
        if (e.button !== 0) return
        // La clase bloquea la selección de texto mientras se arrastra. No se usa
        // preventDefault: el navegador dejaría de emitir el doble clic que restablece el ancho
        document.body.classList.add('redimensionando')
        e.currentTarget.setPointerCapture(e.pointerId)
        arrastre.current = { x: e.clientX, inicio: ancho, ultimo: ancho }
      }}
      onPointerMove={(e) => {
        if (!arrastre.current) return
        const dx = e.clientX - arrastre.current.x
        const valor = limitar(arrastre.current.inicio + (invertido ? -dx : dx))
        arrastre.current.ultimo = valor
        aplicar(valor)
      }}
      onPointerUp={terminar}
      onPointerCancel={terminar}
      onLostPointerCapture={terminar}
      onDoubleClick={() => onCambiar(limitar(porDefecto))}
      onKeyDown={(e) => {
        const crece = invertido ? 'ArrowLeft' : 'ArrowRight'
        const achica = invertido ? 'ArrowRight' : 'ArrowLeft'
        const valor = {
          [crece]: ancho + PASO_TECLADO,
          [achica]: ancho - PASO_TECLADO,
          Home: min,
          End: max(),
        }[e.key]
        if (valor === undefined) return
        e.preventDefault()
        onCambiar(limitar(valor))
      }}
    >
      <span className="asa-redimensionar-linea" />
    </div>
  )
}
