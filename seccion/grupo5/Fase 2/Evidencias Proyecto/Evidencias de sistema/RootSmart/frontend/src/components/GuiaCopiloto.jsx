import { useEffect, useRef } from 'react'
import { Play, X } from 'lucide-react'
import { nombreMes } from '../lib/formato.js'
import './ModalRecuperar.css'
import './ModalUsuarios.css'
import './GuiaCopiloto.css'

const PARTES = [
  ['Qué medir', 'monto pagado, cantidad de siniestros, prima, pólizas emitidas, cuotas vencidas…'],
  ['Cómo agruparlo', 'por región, producto, tipo de siniestro, segmento o por mes'],
  ['Qué período', '«en abril 2026», «el último trimestre», «este año». Sin período usa toda la historia'],
  ['Opcional', '«en mapa», «en barras», «comparado con el mes anterior» o «con el año anterior», «solo Automóvil»'],
]

const PALABRAS = [
  ['gasto, costo, cuánto pagamos', 'monto pagado de siniestros'],
  ['casos, cuántos siniestros', 'cantidad de siniestros'],
  ['lo reclamado', 'monto denunciado'],
  ['ingresos, venta en plata', 'prima directa neta (ya sin anulaciones)'],
  ['ventas, pólizas nuevas', 'pólizas emitidas'],
  ['exposición, capital asegurado', 'monto asegurado'],
  ['morosidad, deuda, atrasos', 'cuotas vencidas sin pagar'],
  ['cobranza', 'cuotas pagadas'],
]

const DESPUES = [
  'Cambia filtros, período o comparación en el panel de arriba: el gráfico se recalcula sin volver a preguntar.',
  'Renombra un gráfico con doble clic en su título (o con el lápiz).',
  'Guárdalo con «Guardar como dashboard» y compártelo desde «Carpetas y compartidos».',
  'Para anticipar los próximos meses, abre «Proyecciones» en el menú de la izquierda.',
]

// Guía de uso del copiloto: cómo pedir un dashboard completo o un gráfico puntual, con
// ejemplos de las áreas del usuario (del catálogo) que se pueden probar con un clic.
export default function GuiaCopiloto({ catalogo, onCerrar, onProbar }) {
  const ref = useRef(null)
  const areas = catalogo?.dominios ?? []

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
  }, [])

  return (
    <dialog
      ref={ref}
      className="modal-recuperar modal-guia"
      aria-labelledby="guia-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="usuarios-caja">
        <header className="usuarios-cabecera">
          <div>
            <h2 id="guia-titulo">Cómo pedir un buen reporte</h2>
            <p className="modal-texto">
              Escribe lo que quieres ver con tus palabras. La IA lo traduce a una consulta del catálogo (no inventa datos ni
              escribe SQL), el sistema la revisa con tus permisos y la base de datos la calcula. Cada respuesta es un gráfico
              que se suma al reporte del centro.
            </p>
          </div>
          <button type="button" className="modal-cerrar usuarios-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
        </header>

        <section className="guia-seccion">
          <h3>1. Para empezar: pide un dashboard completo</h3>
          <p>
            Di el área y el mes, por ejemplo <em>«dashboard de siniestros de abril 2026»</em>. Armo de una vez las cifras clave
            comparadas con el mes anterior, la tendencia del último año para ver si el mes es normal, y dónde se concentra
            (por región, producto y tipo). Cada gráfico trae una frase con lo que dice. También puedes armarlo con un clic
            desde las recomendaciones del chat.
          </p>
        </section>

        <section className="guia-seccion">
          <h3>2. Para un gráfico puntual: una pregunta, un gráfico</h3>
          <p>Una buena pregunta tiene estas partes:</p>
          <dl className="guia-partes">
            {PARTES.map(([parte, detalle]) => (
              <div key={parte}><dt>{parte}</dt><dd>{detalle}</dd></div>
            ))}
          </dl>
          <p className="guia-ejemplo">
            Ejemplo completo: <em>«Monto pagado por región en abril 2026, comparado con el mes anterior, en mapa»</em>.
            Si falta algo, elijo lo más razonable (por ejemplo, líneas para una evolución por mes) o te pregunto.
          </p>
        </section>

        {areas.length > 0 && (
          <section className="guia-seccion">
            <h3>3. Ejemplos de tus áreas</h3>
            <div className="guia-areas">
              {areas.map((a) => (
                <div key={a.codigo} className="guia-area">
                  <strong>{a.nombre}</strong>
                  {[
                    ...(a.dashboard ? [{ pregunta: `Dashboard de ${a.nombre.toLowerCase()} de ${nombreMes(a.dashboard.mes)}`, motivo: a.dashboard.paraQue }] : []),
                    ...a.recomendaciones.slice(0, 3),
                  ].map((r) => (
                    <button key={r.pregunta} type="button" className="guia-probar" title="Probar en el chat" onClick={() => onProbar(r.pregunta)}>
                      <Play size={11} />
                      <span><b>{r.pregunta}</b><small>{r.motivo}</small></span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="guia-seccion">
          <h3>{areas.length > 0 ? '4' : '3'}. Palabras del negocio que entiendo</h3>
          <table className="guia-palabras">
            <tbody>
              {PALABRAS.map(([dices, entiendo]) => (
                <tr key={dices}><td>«{dices}»</td><td>{entiendo}</td></tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="guia-seccion">
          <h3>{areas.length > 0 ? '5' : '4'}. Después de pedirlo</h3>
          <ul>{DESPUES.map((t) => <li key={t}>{t}</li>)}</ul>
          <p className="guia-nota">
            No modifico datos, no muestro datos personales de clientes (RUT, correo, teléfono) y solo consulto las áreas de tu
            usuario. Si un mes no tiene datos, te digo qué meses hay.
          </p>
        </section>
      </div>
    </dialog>
  )
}
