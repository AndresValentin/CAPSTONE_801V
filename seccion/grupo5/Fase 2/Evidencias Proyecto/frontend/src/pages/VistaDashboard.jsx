import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Lock, Pencil, Save, Sparkles, UserCog, X } from 'lucide-react'
import ModalPermisosDashboard from '../components/ModalPermisosDashboard.jsx'
import { TarjetaGrafico } from '../components/ReporteGraficos.jsx'
import {
  abrirDashboard, actualizarDashboard, cerrarSesion, leerSesion, reejecutarReporte, usaBackend,
} from '../lib/api.js'
import { OPCIONES_COMPARAR } from '../lib/analisis.js'
import { tituloGrafico } from '../lib/graficos.js'
import './Dashboard.css'
import '../components/ReporteGraficos.css'
import '../components/Dashboards.css'

const ROLES = { PROPIETARIO: 'Propietario', EDITOR: 'Editor', LECTOR: 'Lector' }

// Selector de comparación de un gráfico. Se desactiva cuando la métrica no lo permite
function SelectorComparar({ grafico, onCambiar, ocupado }) {
  const noComparable = grafico.interpretacion.comparable === 'no'
  return (
    <select
      className="select-comparar"
      aria-label="Comparar con"
      title={noComparable ? 'Esta métrica refleja el estado de hoy: no se compara con otros períodos.' : 'Comparar con otro período'}
      value={grafico.plan.comparar ?? ''}
      disabled={noComparable || ocupado}
      onChange={(e) => onCambiar(grafico, e.target.value)}
    >
      {OPCIONES_COMPARAR.map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
    </select>
  )
}

function GraficoBloqueado({ grafico, onQuitar }) {
  return (
    <article className="chart-card reporte-grafico">
      <header className="reporte-grafico-cabecera">
        <div><h3>{tituloGrafico(grafico)}</h3></div>
        {onQuitar && (
          <div className="reporte-grafico-acciones">
            <button type="button" title="Quitar del dashboard" aria-label="Quitar gráfico del dashboard" onClick={() => onQuitar(grafico)}><X size={15} /></button>
          </div>
        )}
      </header>
      <div className="grafico-bloqueado">
        <Lock size={20} />
        {grafico.sinAcceso
          ? <p><strong>Sin acceso al área {grafico.sinAcceso}.</strong><br />Este gráfico está en el dashboard, pero tu usuario no puede consultar esa área.</p>
          : <p><strong>No se pudo mostrar este gráfico.</strong><br />{grafico.error}</p>}
      </div>
    </article>
  )
}

// Dashboard guardado en una carpeta compartida
export default function VistaDashboard() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [sesion] = useState(leerSesion)
  const [dash, setDash] = useState(null)
  const [graficos, setGraficos] = useState([])
  const [meta, setMeta] = useState({ nombre: '', descripcion: '' })
  const [editandoMeta, setEditandoMeta] = useState(false)
  const [cambios, setCambios] = useState(false)
  const [ocupado, setOcupado] = useState(null) // id del gráfico que se está recalculando
  const [estado, setEstado] = useState({ guardando: false, texto: '', error: false, conflicto: false })
  const [permisosAbierto, setPermisosAbierto] = useState(false)
  const idValido = /^\d{1,9}$/.test(id ?? '')

  const salir = useCallback(() => {
    cerrarSesion()
    navigate('/', { replace: true })
  }, [navigate])

  const cargar = useCallback(() => {
    abrirDashboard(id)
      .then((d) => {
        setDash(d)
        // El backend devuelve el título guardado en `pregunta`
        setGraficos(d.graficos.map((g) => ({ ...g, titulo: g.pregunta })))
        setMeta({ nombre: d.nombre, descripcion: d.descripcion })
        setCambios(false)
        setEstado({ guardando: false, texto: '', error: false, conflicto: false })
      })
      .catch((err) => {
        if (err.estado === 401) salir()
        else setEstado({ guardando: false, texto: err.message || 'No se pudo abrir el dashboard.', error: true, conflicto: false })
      })
  }, [id, salir])

  useEffect(() => {
    if (!usaBackend || !sesion) {
      navigate('/', { replace: true })
      return
    }
    // Una URL como /dashboards/abc no llega al backend (respondería 422)
    if (idValido) cargar()
  }, [cargar, navigate, sesion, idValido])

  const puedeEditar = dash && dash.rol !== 'LECTOR'

  async function cambiarComparacion(grafico, comparar) {
    setOcupado(grafico.id)
    try {
      const r = await reejecutarReporte(grafico.pregunta, { ...grafico.plan, comparar })
      if (r.estado !== 'validado') {
        setEstado((s) => ({ ...s, texto: r.motivo, error: true }))
        return
      }
      setGraficos((lista) => lista.map((g) => (g.id === grafico.id
        ? { ...g, plan: r.plan, interpretacion: r.interpretacion, resultado: r.resultado }
        : g)))
      if (puedeEditar) setCambios(true)
    } catch (err) {
      if (err.estado === 401) salir()
      else setEstado((s) => ({ ...s, texto: err.message || 'No se pudo recalcular el gráfico.', error: true }))
    } finally {
      setOcupado(null)
    }
  }

  function quitar(grafico) {
    setGraficos((lista) => lista.filter((g) => g.id !== grafico.id))
    setCambios(true)
  }

  function renombrar(grafico, titulo) {
    setGraficos((lista) => lista.map((g) => (g.id === grafico.id ? { ...g, titulo } : g)))
    setCambios(true)
  }

  async function guardar() {
    const guardables = graficos.filter((g) => g.plan)
    if (guardables.length === 0) {
      setEstado((s) => ({ ...s, texto: 'Un dashboard necesita al menos un gráfico. Para borrarlo, hazlo desde la carpeta.', error: true }))
      return
    }
    setEstado({ guardando: true, texto: '', error: false, conflicto: false })
    try {
      const r = await actualizarDashboard(dash.id, {
        nombre: meta.nombre.trim() || dash.nombre,
        descripcion: meta.descripcion.trim(),
        version: dash.version,
        graficos: guardables.map((g) => ({ titulo: tituloGrafico(g).slice(0, 200), plan: g.plan })),
      })
      setDash((d) => ({ ...d, version: r.version, nombre: meta.nombre.trim() || d.nombre, descripcion: meta.descripcion.trim() }))
      setCambios(false)
      setEditandoMeta(false)
      setEstado({ guardando: false, texto: 'Cambios guardados para todos los miembros de la carpeta.', error: false, conflicto: false })
    } catch (err) {
      if (err.estado === 401) {
        salir()
        return
      }
      setEstado({ guardando: false, texto: err.message || 'No se pudieron guardar los cambios.', error: true, conflicto: err.estado === 409 })
    }
  }

  return (
    <div className="dashboard-screen">
      <header className="dashboard-header">
        <div className="brand">
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
          <span className="brand-name">BI Copilot · Dashboards</span>
        </div>
        <div className="header-meta">
          <Link className="btn-cabecera" to="/dashboards"><ArrowLeft size={14} /> Carpetas</Link>
          <Link className="btn-cabecera" to="/dashboard">Copiloto</Link>
        </div>
      </header>

      <main className="vista-dashboard">
        {estado.texto && (
          <p className={`biblio-aviso ${estado.error ? 'biblio-aviso-error' : ''}`} role="status">
            {estado.texto}
            {estado.conflicto && <> <button type="button" className="link-btn" onClick={() => { setDash(null); cargar() }}>Abrir la versión más reciente</button></>}
          </p>
        )}

        {!idValido && (
          <p className="biblio-vacio">Este dashboard no existe. <Link to="/dashboards">Volver a las carpetas</Link></p>
        )}
        {idValido && !dash && !estado.error && <p className="biblio-vacio">Calculando los gráficos con datos actualizados…</p>}
        {!dash && estado.error && !estado.conflicto && <p className="biblio-vacio"><Link to="/dashboards">Volver a las carpetas</Link></p>}

        {dash && (
          <>
            <div className="biblio-cabecera">
              {editandoMeta ? (
                <div className="biblio-form">
                  <input aria-label="Nombre del dashboard" maxLength={100} value={meta.nombre} onChange={(e) => { setMeta({ ...meta, nombre: e.target.value }); setCambios(true) }} />
                  <textarea aria-label="Descripción del dashboard" rows={2} maxLength={500} placeholder="Descripción" value={meta.descripcion} onChange={(e) => { setMeta({ ...meta, descripcion: e.target.value }); setCambios(true) }} />
                </div>
              ) : (
                <div>
                  <h1>{meta.nombre}</h1>
                  {meta.descripcion && <p>{meta.descripcion}</p>}
                  <div className="biblio-etiquetas">
                    <span className="biblio-etiqueta">Carpeta: {dash.carpetaNombre}</span>
                    <span className="biblio-etiqueta">Tu rol: {ROLES[dash.rol]}</span>
                    <span className="biblio-etiqueta">Actualizado {dash.actualizado}{dash.actualizadoPor ? ` por ${dash.actualizadoPor}` : ''}</span>
                  </div>
                </div>
              )}
              <div className="biblio-acciones">
                {dash.rol === 'PROPIETARIO' && (
                  <button type="button" className="biblio-boton biblio-boton-sec" onClick={() => setPermisosAbierto(true)}>
                    <UserCog size={15} /> Permisos
                  </button>
                )}
                {puedeEditar && !editandoMeta && (
                  <button type="button" className="biblio-boton biblio-boton-sec" onClick={() => setEditandoMeta(true)}><Pencil size={15} /> Editar datos</button>
                )}
                {puedeEditar && (
                  <button type="button" className="biblio-boton" onClick={guardar} disabled={!cambios || estado.guardando}>
                    <Save size={15} /> {estado.guardando ? 'Guardando…' : 'Guardar cambios'}
                  </button>
                )}
              </div>
            </div>

            <p className="biblio-aviso">
              Los datos se calcularon recién, con tus permisos.{' '}
              {puedeEditar
                ? 'Puedes renombrar gráficos (lápiz o doble clic en el título), cambiar su comparación o quitarlos, y guardar para todos.'
                : 'Puedes cambiar la comparación de cada gráfico para explorar; como lector, los cambios no se guardan.'}
            </p>

            <div className="reporte-grilla">
              {graficos.map((g) => (g.resultado ? (
                <TarjetaGrafico
                  key={g.id}
                  reporte={g}
                  onQuitar={puedeEditar ? quitar : undefined}
                  onRenombrar={puedeEditar ? renombrar : undefined}
                  controles={<SelectorComparar grafico={g} onCambiar={cambiarComparacion} ocupado={ocupado !== null} />}
                />
              ) : (
                <GraficoBloqueado key={g.id} grafico={g} onQuitar={puedeEditar ? quitar : undefined} />
              )))}
            </div>
          </>
        )}
      </main>

      {permisosAbierto && dash && (
        <ModalPermisosDashboard dashboard={dash} onCerrar={() => setPermisosAbierto(false)} onSesionExpirada={salir} />
      )}
    </div>
  )
}
