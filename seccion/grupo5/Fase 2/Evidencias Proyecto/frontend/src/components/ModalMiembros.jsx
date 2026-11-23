import { useCallback, useEffect, useRef, useState } from 'react'
import { UserPlus, X } from 'lucide-react'
import { directorioUsuarios, guardarMiembro, listarMiembros } from '../lib/api.js'
import './ModalRecuperar.css'
import './ModalUsuarios.css'
import './Dashboards.css'

const ROLES = { PROPIETARIO: 'Propietario', EDITOR: 'Editor', LECTOR: 'Lector' }

// Miembros de una carpeta. Todos los miembros ven la lista; solo el propietario la cambia.
export default function ModalMiembros({ carpeta, onCerrar, onCambio, onSesionExpirada }) {
  const ref = useRef(null)
  const esPropietario = carpeta.rol === 'PROPIETARIO'
  const [miembros, setMiembros] = useState(null)
  const [directorio, setDirectorio] = useState([])
  const [nuevo, setNuevo] = useState({ usuario: '', rol: 'LECTOR' })
  const [aviso, setAviso] = useState({ texto: '', error: false })

  const fallo = useCallback((err, porDefecto) => {
    if (err.estado === 401) onSesionExpirada()
    else setAviso({ texto: err.message || porDefecto, error: true })
  }, [onSesionExpirada])

  const cargar = useCallback(() => listarMiembros(carpeta.id)
    .then((r) => setMiembros(r.miembros))
    .catch((err) => fallo(err, 'No se pudieron cargar los miembros.')), [carpeta.id, fallo])

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
    cargar()
    if (esPropietario) directorioUsuarios().then((r) => setDirectorio(r.usuarios)).catch(() => {})
  }, [cargar, esPropietario])

  async function guardar(usuario, rol, texto) {
    setAviso({ texto: '', error: false })
    try {
      await guardarMiembro(carpeta.id, usuario, rol)
      setAviso({ texto, error: false })
      setNuevo({ usuario: '', rol: 'LECTOR' })
      await cargar()
      onCambio()
    } catch (err) {
      fallo(err, 'No se pudo guardar el cambio.')
    }
  }

  const disponibles = directorio.filter((u) => !miembros?.some((m) => m.usuario === u.usuario))

  return (
    <dialog
      ref={ref}
      className="modal-recuperar modal-miembros"
      aria-labelledby="miembros-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="usuarios-caja">
        <header className="usuarios-cabecera">
          <div>
            <h2 id="miembros-titulo">Miembros de «{carpeta.nombre}»</h2>
            <p className="modal-texto">
              Los lectores ven los dashboards; los editores además los crean, cambian y borran. Compartir no da
              acceso a otras áreas: cada persona ve solo los gráficos de las áreas que puede consultar.
              {esPropietario && ' Para dar un rol distinto en un dashboard puntual, ábrelo y usa «Permisos».'}
            </p>
          </div>
          <button type="button" className="modal-cerrar usuarios-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
        </header>

        {aviso.texto && <p className={aviso.error ? 'form-error' : 'usuarios-ok'} role="status">{aviso.texto}</p>}

        {esPropietario && (
          <div className="miembros-agregar">
            <select aria-label="Persona" value={nuevo.usuario} onChange={(e) => setNuevo((n) => ({ ...n, usuario: e.target.value }))}>
              <option value="">Elige una persona…</option>
              {disponibles.map((u) => <option key={u.usuario} value={u.usuario}>{u.nombre} ({u.usuario})</option>)}
            </select>
            <select aria-label="Rol" value={nuevo.rol} onChange={(e) => setNuevo((n) => ({ ...n, rol: e.target.value }))}>
              <option value="LECTOR">Lector</option>
              <option value="EDITOR">Editor</option>
            </select>
            <button
              type="button"
              className="biblio-boton"
              disabled={!nuevo.usuario}
              onClick={() => guardar(nuevo.usuario, nuevo.rol, 'Persona agregada a la carpeta.')}
            >
              <UserPlus size={15} /> Agregar
            </button>
          </div>
        )}

        {!miembros && !aviso.error && <p className="modal-texto">Cargando…</p>}

        {miembros && (
          <div className="usuarios-tabla">
            <table>
              <thead>
                <tr><th>Persona</th><th>Rol</th><th /></tr>
              </thead>
              <tbody>
                {miembros.map((m) => (
                  <tr key={m.usuario}>
                    <td><strong>{m.nombre}</strong><span>{m.usuario}</span></td>
                    <td>
                      {esPropietario && m.rol !== 'PROPIETARIO' ? (
                        <select
                          className="miembros-rol"
                          aria-label={`Rol de ${m.nombre}`}
                          value={m.rol}
                          onChange={(e) => guardar(m.usuario, e.target.value, `Rol de ${m.nombre} actualizado.`)}
                        >
                          <option value="LECTOR">Lector</option>
                          <option value="EDITOR">Editor</option>
                        </select>
                      ) : ROLES[m.rol]}
                    </td>
                    <td className="usuarios-botones">
                      {esPropietario && m.rol !== 'PROPIETARIO' && (
                        <button type="button" title="Quitar de la carpeta" aria-label={`Quitar a ${m.nombre}`} onClick={() => guardar(m.usuario, '', `${m.nombre} ya no es miembro.`)}>
                          <X size={15} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </dialog>
  )
}
