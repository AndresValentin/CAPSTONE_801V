import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Folder, FolderOpen, FolderPlus, Pencil, Sparkles, Trash2, Users } from 'lucide-react'
import ModalMiembros from '../components/ModalMiembros.jsx'
import {
  cerrarSesion, crearCarpeta, editarCarpeta, eliminarCarpeta, eliminarDashboard, leerSesion, listarCarpetas, usaBackend,
} from '../lib/api.js'
import './Dashboard.css'
import '../components/Dashboards.css'

const ROLES = { PROPIETARIO: 'Propietario', EDITOR: 'Editor', LECTOR: 'Lector' }

function FormCarpeta({ inicial, onGuardar, onCancelar }) {
  const [datos, setDatos] = useState(inicial)
  return (
    <form className="biblio-form" onSubmit={(e) => { e.preventDefault(); if (datos.nombre.trim()) onGuardar(datos) }}>
      <input aria-label="Nombre de la carpeta" maxLength={100} value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} />
      <textarea aria-label="Descripción de la carpeta" rows={2} maxLength={500} placeholder="Descripción: para qué es y quién la usa" value={datos.descripcion} onChange={(e) => setDatos({ ...datos, descripcion: e.target.value })} />
      <div className="biblio-acciones">
        <button type="submit" className="biblio-boton">Guardar</button>
        <button type="button" className="biblio-boton biblio-boton-sec" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  )
}

// Repositorio compartido de dashboards: carpetas con miembros y roles
export default function Biblioteca() {
  const navigate = useNavigate()
  const [sesion] = useState(leerSesion)
  const [carpetas, setCarpetas] = useState(null)
  // /dashboards?carpeta=ID (desde el menú lateral del copiloto) abre esa carpeta
  const [parametros] = useSearchParams()
  const [activaId, setActivaId] = useState(() => Number(parametros.get('carpeta')) || null)
  const [nueva, setNueva] = useState('')
  const [editando, setEditando] = useState(false)
  const [miembrosAbierto, setMiembrosAbierto] = useState(false)
  const [aviso, setAviso] = useState({ texto: '', error: false })

  const salir = useCallback(() => {
    cerrarSesion()
    navigate('/', { replace: true })
  }, [navigate])

  const fallo = useCallback((err, porDefecto) => {
    if (err.estado === 401) salir()
    else setAviso({ texto: err.message || porDefecto, error: true })
  }, [salir])

  const cargar = useCallback(() => listarCarpetas()
    .then(({ carpetas: lista }) => {
      setCarpetas(lista)
      // Se abre la carpeta pedida en la URL o la que estaba abierta; si no, la primera propia
      setActivaId((actual) => (lista.some((c) => c.id === actual)
        ? actual
        : (lista.find((c) => c.rol === 'PROPIETARIO') ?? lista[0])?.id ?? null))
    })
    .catch((err) => fallo(err, 'No se pudieron cargar las carpetas.')), [fallo])

  useEffect(() => {
    if (!usaBackend || !sesion) {
      navigate('/', { replace: true })
      return
    }
    cargar()
  }, [cargar, navigate, sesion])

  const activa = carpetas?.find((c) => c.id === activaId)
  const puedeEditar = activa && activa.rol !== 'LECTOR'

  async function ejecutar(accion, textoOk, porDefecto) {
    setAviso({ texto: '', error: false })
    try {
      const r = await accion()
      if (textoOk) setAviso({ texto: textoOk, error: false })
      await cargar()
      return r
    } catch (err) {
      fallo(err, porDefecto)
      return null
    }
  }

  async function crear(e) {
    e.preventDefault()
    if (!nueva.trim()) return
    const r = await ejecutar(() => crearCarpeta({ nombre: nueva.trim(), descripcion: '' }), 'Carpeta creada. Agrega miembros para compartirla.', 'No se pudo crear la carpeta.')
    if (r) {
      setNueva('')
      setActivaId(r.id)
    }
  }

  async function guardarCarpeta(datos) {
    const r = await ejecutar(() => editarCarpeta(activa.id, { nombre: datos.nombre.trim(), descripcion: datos.descripcion.trim() }), 'Carpeta actualizada.', 'No se pudo guardar la carpeta.')
    if (r) setEditando(false)
  }

  function borrarCarpeta() {
    const n = activa.dashboards.length
    if (!window.confirm(`¿Eliminar la carpeta «${activa.nombre}»${n ? ` y sus ${n} dashboards` : ''}? Los miembros dejarán de verla.`)) return
    ejecutar(() => eliminarCarpeta(activa.id), 'Carpeta eliminada.', 'No se pudo eliminar la carpeta.')
  }

  function borrarDashboard(e, d) {
    // El botón está dentro del enlace a la tarjeta: no debe abrir el dashboard
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm(`¿Eliminar el dashboard «${d.nombre}» para todos los miembros?`)) return
    ejecutar(() => eliminarDashboard(d.id), 'Dashboard eliminado.', 'No se pudo eliminar el dashboard.')
  }

  return (
    <div className="dashboard-screen">
      <header className="dashboard-header">
        <div className="brand">
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
          <span className="brand-name">RootSmart · Dashboards</span>
        </div>
        <div className="header-meta">
          <Link className="btn-cabecera" to="/dashboard"><ArrowLeft size={14} /> Volver al asistente</Link>
        </div>
      </header>

      <div className="biblio">
        <aside className="biblio-carpetas">
          <form className="biblio-nueva" onSubmit={crear}>
            <input aria-label="Nombre de la carpeta nueva" placeholder="Nueva carpeta" maxLength={100} value={nueva} onChange={(e) => setNueva(e.target.value)} />
            <button type="submit" className="biblio-boton" title="Crear carpeta" aria-label="Crear carpeta" disabled={!nueva.trim()}><FolderPlus size={15} /></button>
          </form>
          {carpetas && [
            ['Mis carpetas', carpetas.filter((c) => c.rol === 'PROPIETARIO'), 'Aún no creas carpetas.'],
            ['Compartidas conmigo', carpetas.filter((c) => c.rol !== 'PROPIETARIO'), 'Nadie ha compartido carpetas contigo.'],
          ].map(([titulo, lista, vacio]) => (
            <nav key={titulo} className="biblio-lista" aria-label={titulo}>
              <h2>{titulo}</h2>
              {lista.length === 0 && <p className="biblio-lista-vacia">{vacio}</p>}
              {lista.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="biblio-carpeta"
                  aria-current={c.id === activaId}
                  onClick={() => { setActivaId(c.id); setEditando(false) }}
                >
                  {c.rol === 'PROPIETARIO' ? <Folder size={16} /> : <FolderOpen size={16} />}
                  <span className="biblio-carpeta-texto">
                    <strong>{c.nombre}</strong>
                    <span>
                      {c.rol === 'PROPIETARIO' ? '' : `De ${c.propietario} · ${ROLES[c.rol]} · `}
                      {c.dashboards.length} {c.dashboards.length === 1 ? 'dashboard' : 'dashboards'}
                    </span>
                  </span>
                </button>
              ))}
            </nav>
          ))}
        </aside>

        <main className="biblio-main">
          {aviso.texto && <p className={`biblio-aviso ${aviso.error ? 'biblio-aviso-error' : ''}`} role="status">{aviso.texto}</p>}

          {!carpetas && !aviso.error && <p className="biblio-vacio">Cargando carpetas…</p>}

          {carpetas?.length === 0 && (
            <p className="biblio-vacio">
              Aún no tienes carpetas. Crea una a la izquierda o guarda un reporte desde el chat con «Guardar como dashboard».
            </p>
          )}

          {activa && (
            <>
              <div className="biblio-cabecera">
                {editando ? (
                  <FormCarpeta inicial={{ nombre: activa.nombre, descripcion: activa.descripcion }} onGuardar={guardarCarpeta} onCancelar={() => setEditando(false)} />
                ) : (
                  <div>
                    <h1>{activa.nombre}</h1>
                    {activa.descripcion && <p>{activa.descripcion}</p>}
                    <div className="biblio-etiquetas">
                      <span className="biblio-etiqueta">Tu rol: {ROLES[activa.rol]}</span>
                      <span className="biblio-etiqueta">Propietario: {activa.propietario}</span>
                      <span className="biblio-etiqueta">{activa.miembros} {activa.miembros === 1 ? 'miembro' : 'miembros'}</span>
                    </div>
                  </div>
                )}
                {!editando && (
                  <div className="biblio-acciones">
                    <button type="button" className="biblio-boton biblio-boton-sec" onClick={() => setMiembrosAbierto(true)}>
                      <Users size={15} /> {activa.rol === 'PROPIETARIO' ? 'Compartir' : 'Miembros'}
                    </button>
                    {activa.rol === 'PROPIETARIO' && (
                      <>
                        <button type="button" className="biblio-boton biblio-boton-sec" onClick={() => setEditando(true)}><Pencil size={15} /> Editar</button>
                        <button type="button" className="biblio-boton biblio-boton-peligro" onClick={borrarCarpeta}><Trash2 size={15} /> Eliminar</button>
                      </>
                    )}
                  </div>
                )}
              </div>

              {activa.dashboards.length === 0 ? (
                <p className="biblio-vacio">
                  Esta carpeta aún no tiene dashboards.{puedeEditar ? ' Guarda uno desde el chat con «Guardar como dashboard».' : ''}
                </p>
              ) : (
                <div className="biblio-grilla">
                  {activa.dashboards.map((d) => (
                    <Link key={d.id} className="biblio-tarjeta" to={`/dashboards/${d.id}`}>
                      <h3>{d.nombre}</h3>
                      {d.descripcion && <p>{d.descripcion}</p>}
                      {d.rol !== activa.rol && (
                        <span className="biblio-tarjeta-permiso">{d.rol === 'EDITOR' ? 'Puedes editar este dashboard' : 'Solo lectura en este dashboard'}</span>
                      )}
                      {activa.rol === 'PROPIETARIO' && d.excepciones > 0 && (
                        <span className="biblio-tarjeta-permiso">
                          {d.excepciones} {d.excepciones === 1 ? 'persona con permiso propio' : 'personas con permiso propio'}
                        </span>
                      )}
                      <span className="biblio-tarjeta-meta">
                        {d.graficos} {d.graficos === 1 ? 'gráfico' : 'gráficos'} · actualizado {d.actualizado}{d.actualizadoPor ? ` por ${d.actualizadoPor}` : ''}
                      </span>
                      {(d.rol ?? activa.rol) !== 'LECTOR' && (
                        <button type="button" className="biblio-tarjeta-borrar" title="Eliminar dashboard" aria-label={`Eliminar ${d.nombre}`} onClick={(e) => borrarDashboard(e, d)}>
                          <Trash2 size={14} />
                        </button>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {miembrosAbierto && activa && (
        <ModalMiembros carpeta={activa} onCerrar={() => setMiembrosAbierto(false)} onCambio={cargar} onSesionExpirada={salir} />
      )}
    </div>
  )
}
