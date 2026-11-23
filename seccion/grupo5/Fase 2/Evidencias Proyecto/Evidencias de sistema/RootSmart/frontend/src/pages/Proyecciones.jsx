import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ArrowLeft, LayoutDashboard, Minus, Sparkles, Star, TrendingDown, TrendingUp } from 'lucide-react'
import { claveSerie, useProyecciones } from '../hooks/useProyecciones.js'
import { cerrarSesion, leerSesion, usaBackend } from '../lib/api.js'
import { serieConAnalisis } from '../lib/analisis.js'
import { formatCLPCorto, formatMetrica, mesCorto, nombreMes } from '../lib/formato.js'
import { ESTILO_TOOLTIP } from '../lib/graficos.js'
import './Dashboard.css'
import '../components/Dashboards.css'
import './Proyecciones.css'

const MESES_EN_GRAFICO = 24
const PORCENTAJE = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 })

const SENTIDOS = {
  baja: { texto: 'A la baja', icono: TrendingDown },
  sube: { texto: 'Al alza', icono: TrendingUp },
  estable: { texto: 'Estable', icono: Minus },
}

// Hacia dónde va: estable si la tendencia mueve menos del 2 % del nivel de los últimos meses
function sentidoDe(proyeccion, serie) {
  const ultimos = serie.slice(-3).map((f) => Math.abs(f.valor ?? 0))
  const nivel = ultimos.reduce((a, b) => a + b, 0) / (ultimos.length || 1)
  const tendencia = proyeccion.tendencia ?? 0
  if (!nivel || Math.abs(tendencia) / nivel < 0.02) return 'estable'
  return tendencia > 0 ? 'sube' : 'baja'
}

// Qué tan confiable es, según cuánto se equivocó pronosticando los últimos meses
function confianzaDe(acierto) {
  const error = acierto?.error_relativo
  if (error === null || error === undefined) return null
  const pct = PORCENTAJE.format(error * 100)
  // Aunque haya acertado, si los últimos meses parecen carga incompleta no se puede confiar del todo
  if (acierto.datos_dudosos) {
    return { nivel: 'Media', clase: 'media', consejo: 'Pero los últimos meses cayeron de golpe: antes de usarla, revisa si están completos en la base.', pct }
  }
  if (error <= 0.1) return { nivel: 'Alta', clase: 'alta', consejo: 'Sirve para planificar.', pct }
  if (error <= 0.25) return { nivel: 'Media', clase: 'media', consejo: 'Úsala como referencia y mira el rango.', pct }
  return { nivel: 'Baja', clase: 'baja', consejo: 'Tómala solo como orientación: la serie cambia mucho de un mes a otro.', pct }
}

function capitalizar(texto) {
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

function ListaSeries({ p }) {
  const areas = [...new Set(p.series.map((s) => s.area))]
  return areas.map((area) => (
    <nav key={area} className="proy-grupo" aria-label={area}>
      <h2>{area}</h2>
      {p.series.filter((s) => s.area === area).map((s) => (
        <button
          key={claveSerie(s)}
          type="button"
          className="proy-opcion"
          aria-current={claveSerie(s) === p.elegida}
          title={s.motivo || s.etiqueta}
          onClick={() => p.elegir(claveSerie(s))}
        >
          <span>{s.etiqueta}</span>
          {s.recomendada && <Star size={12} className="proy-estrella" aria-label="Recomendada" />}
        </button>
      ))}
    </nav>
  ))
}

function Grafico({ respuesta, proyeccion, moneda }) {
  const fmt = (v) => formatMetrica(v, moneda)
  const datos = serieConAnalisis(respuesta.resultado.serie.slice(-MESES_EN_GRAFICO), proyeccion)
  const conAtipicos = proyeccion.anomalias.length > 0
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={datos} margin={{ top: 10, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey="categoria" tickFormatter={mesCorto} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} interval="preserveStartEnd" tickLine={false} axisLine={false} />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
          tickFormatter={(v) => (moneda ? formatCLPCorto(v) : v.toLocaleString('es-CL'))}
          tickLine={false}
          axisLine={false}
          width={64}
        />
        <Tooltip
          {...ESTILO_TOOLTIP}
          labelFormatter={nombreMes}
          formatter={(v, nombre) => [Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])}` : v == null ? '—' : fmt(v), nombre]}
        />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
        <Area dataKey="rango" name="Rango probable" stroke="none" fill="var(--chart-proyeccion)" fillOpacity={0.14} isAnimationActive={false} legendType="none" />
        <Line dataKey="valor" name="Real" stroke="var(--color-primary)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        <Line dataKey="proyectado" name="Proyección" stroke="var(--chart-proyeccion)" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3 }} isAnimationActive={false} />
        {conAtipicos && <Scatter dataKey="atipico" name="Mes fuera de lo normal" fill="var(--color-danger)" isAnimationActive={false} />}
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function Detalle({ p, onAgregar }) {
  const { respuesta, serie } = p
  const proyeccion = respuesta?.resultado?.proyeccion
  if (p.cargando) return <p className="proy-estado">Calculando con los datos de la base…</p>
  if (p.error) return <p className="proy-estado proy-estado-error" role="alert">{p.error}</p>
  if (!serie || !proyeccion) return null
  if (proyeccion.omitida) return <p className="proy-estado">{proyeccion.omitida}</p>

  const fmt = (v) => formatMetrica(v, serie.moneda)
  const meses = proyeccion.meses
  const sentido = sentidoDe(proyeccion, respuesta.resultado.serie)
  const { texto: textoSentido, icono: IconoSentido } = SENTIDOS[sentido]
  const tendencia = Math.abs(proyeccion.tendencia ?? 0)
  const confianza = confianzaDe(proyeccion.acierto)
  // La conclusión en una frase (los valores mes a mes ya están en las tarjetas)
  const ultimo = meses.at(-1)
  const enCero = meses.find((m) => m.valor === 0)
  const conclusion = {
    estable: `Se mantiene estable, en torno a ${fmt(meses[0].valor)} por mes.`,
    baja: enCero
      ? `Viene a la baja: ${fmt(tendencia)} menos cada mes. Si sigue así, llega a cero en ${nombreMes(enCero.mes)}.`
      : `Viene a la baja: ${fmt(tendencia)} menos cada mes. Para ${nombreMes(ultimo.mes)} se esperan ${fmt(ultimo.valor)}.`,
    sube: `Viene al alza: ${fmt(tendencia)} más cada mes. Para ${nombreMes(ultimo.mes)} se esperan ${fmt(ultimo.valor)}.`,
  }[sentido]
  const avisos = [
    ...proyeccion.anomalias.map((a) => `${capitalizar(nombreMes(a.mes))} se salió de lo normal: ${fmt(a.valor)} cuando se esperaba ${fmt(a.esperado)}.`),
    ...proyeccion.notas,
  ]

  return (
    <article className="proy-detalle">
      <header className="proy-cabecera">
        <div>
          <span className="proy-area">{serie.area}</span>
          <h1>{serie.etiqueta}</h1>
          {serie.motivo && <p>{serie.motivo}</p>}
        </div>
        <div className="proy-cabecera-acciones">
          <button type="button" className="biblio-boton biblio-boton-sec" onClick={onAgregar}>
            <LayoutDashboard size={15} /> Agregar al reporte
          </button>
          <span className="proy-actualizado">
            Se actualiza solo · datos hasta {nombreMes(proyeccion.base.hasta)}
          </span>
        </div>
      </header>

      <section className="proy-resumen">
        <span className={`proy-sentido proy-sentido-${sentido}`}><IconoSentido size={14} /> {textoSentido}</span>
        <p>{conclusion}</p>
      </section>

      <div className="proy-meses">
        {meses.map((m, i) => (
          <div key={m.mes} className={`proy-mes ${i === 0 ? 'proy-mes-proximo' : ''}`}>
            <span>{capitalizar(nombreMes(m.mes))}</span>
            <strong>{fmt(m.valor)}</strong>
            <small>entre {fmt(m.min)} y {fmt(m.max)}</small>
          </div>
        ))}
      </div>

      <div className="proy-grafico">
        <Grafico respuesta={respuesta} proyeccion={proyeccion} moneda={serie.moneda} />
      </div>

      <div className="proy-columnas">
        {confianza && (
          <section className="proy-tarjeta">
            <h3>¿Qué tan confiable es? <span className={`proy-confianza proy-confianza-${confianza.clase}`}>{confianza.nivel}</span></h3>
            <p>
              En los últimos {proyeccion.acierto.meses} meses, el pronóstico de cada mes, hecho solo con los datos anteriores,
              se equivocó en promedio un {confianza.pct} %. {confianza.consejo}
            </p>
          </section>
        )}
        <section className="proy-tarjeta">
          <h3>Ten en cuenta</h3>
          {avisos.length === 0
            ? <p>Sin alertas: los últimos meses se ven normales.</p>
            : <ul>{avisos.map((a) => <li key={a}>{a}</li>)}</ul>}
        </section>
      </div>

      <details className="proy-como">
        <summary>¿Cómo se calcula?</summary>
        <p>
          Cada mes, el cálculo mira lo que pasó y ajusta dos cosas: el <strong>nivel</strong> (cuánto hay hoy) y la
          <strong> tendencia</strong> (cuánto sube o baja por mes). Da más peso a los meses recientes, así que si la serie viene
          bajando, la proyección sigue bajando y se va frenando; no vuelve sola al promedio de años anteriores.
        </p>
        <p>
          Usa {proyeccion.base.meses} meses de la base ({nombreMes(proyeccion.base.desde)} a {nombreMes(proyeccion.base.hasta)})
          y se vuelve a calcular solo cuando llegan datos nuevos. El rango es donde debería caer la cifra real la mayoría de
          las veces. Es el mismo tipo de método que usa Power BI para sus pronósticos (suavizamiento exponencial).
        </p>
      </details>
    </article>
  )
}

// Pantalla del módulo "Proyecciones": elegir qué anticipar y ver el pronóstico de los
// próximos 3 meses en palabras simples. Se recalcula sola con los datos de la base.
export default function Proyecciones() {
  const navigate = useNavigate()
  const [sesion] = useState(leerSesion)
  const salir = useCallback(() => {
    cerrarSesion()
    navigate('/', { replace: true })
  }, [navigate])
  const p = useProyecciones(salir)
  const iniciado = useRef(false)
  const actual = useRef(p)

  useEffect(() => {
    actual.current = p
  })

  useEffect(() => {
    if (!usaBackend || !sesion) {
      navigate('/', { replace: true })
      return
    }
    if (iniciado.current) return
    iniciado.current = true
    p.iniciar()
  })

  // Mientras la pantalla está abierta, vuelve a calcular la serie elegida cada pocos
  // minutos: si entró un mes nuevo a la base, la proyección avanza sola
  useEffect(() => {
    const id = setInterval(() => actual.current.actualizar(), actual.current.VIGENCIA_MS)
    return () => clearInterval(id)
  }, [])

  function agregarAlReporte() {
    navigate('/dashboard', { state: { proyeccion: { respuesta: p.respuesta, serie: p.serie } } })
  }

  return (
    <div className="dashboard-screen">
      <header className="dashboard-header">
        <div className="brand">
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
          <span className="brand-name">RootSmart · Proyecciones</span>
        </div>
        <div className="header-meta">
          <Link className="btn-cabecera" to="/dashboard"><ArrowLeft size={14} /> Volver al asistente</Link>
        </div>
      </header>

      <div className="proy-pagina">
        <aside className="proy-lateral">
          <p className="proy-lateral-titulo">¿Qué quieres anticipar?</p>
          {p.series === null && !p.error && <p className="proy-lateral-vacio">Cargando…</p>}
          {p.series?.length === 0 && <p className="proy-lateral-vacio">Tus áreas no tienen series que se puedan proyectar.</p>}
          {p.series?.length > 0 && <ListaSeries p={p} />}
          {p.series?.some((s) => s.recomendada) && (
            <p className="proy-lateral-nota"><Star size={11} className="proy-estrella" /> las más útiles para decidir</p>
          )}
        </aside>

        <main className="proy-main">
          {p.series === null && p.error && <p className="proy-estado proy-estado-error" role="alert">{p.error}</p>}
          <Detalle p={p} onAgregar={agregarAlReporte} />
        </main>
      </div>
    </div>
  )
}
