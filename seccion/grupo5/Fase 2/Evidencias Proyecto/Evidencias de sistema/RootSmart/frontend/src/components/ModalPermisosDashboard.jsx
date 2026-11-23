import { useCallback, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { guardarPermisoDashboard, listarPermisosDashboard } from '../lib/api.js'
import './ModalRecuperar.css'
import './ModalUsuarios.css'
import './Dashboards.css'

const ROLES = { EDITOR: 'Editor', LECTOR: 'Lector' }

// Permiso por dashboard: el propietario de la carpeta da a un miembro un rol distinto
// en este dashboard (por ejemplo, un lector de la carpeta que puede editar solo este).
// Las personas se agregan desde «Compartir» en la carpeta; aquí solo se ajustan.
export default function ModalPermisosDashboard({ dashboard, onCerrar, onSesionExpirada }) {
  const ref = useRef(null)
  const [miembros, setMiembros] = useState(null)
  const [aviso, setAviso] = useState({ texto: '', error: false })
  const [guardando, setGuardando] = useState('')
  const sesionExpirada = useRef(onSesionExpirada)
  useEffect(() => { sesionExpirada.current = onSesionExpirada })

  const fallo = useCallback((err, porDefecto) => {
    if (err.estado === 401) sesionExpirada.current?.()
    else setAviso({ texto: err.message || porDefecto, error: true })
  }, [])

  const cargar = useCallback(() => listarPermisosDashboard(dashboard.id)
    .then((r) => setMiembros(r.miembros))
    .catch((err) => fallo(err, 'No se pudieron cargar los permisos.')), [dashboard.id, fallo])

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
    cargar()
  }, [cargar])

  async function cambiar(m, rol) {
    setAviso({ texto: '', error: false })
    setGuardando(m.usuario)
    try {
      await guardarPermisoDashboard(dashboard.id, m.usuario, rol)
      setAviso({
        texto: rol
          ? `${m.nombre} ahora es ${ROLES[rol].toLowerCase()} en este dashboard.`
          : `${m.nombre} vuelve a su rol de la carpeta (${ROLES[m.rolCarpeta].toLowerCase()}).`,
        error: false,
      })
      await cargar()
    } catch (err) {
      fallo(err, 'No se pudo guardar el permiso.')
    } finally {
      setGuardando('')
    }
  }

  return (
    <dialog
      ref={ref}
      className="modal-recuperar modal-miembros"
      aria-labelledby="permisos-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="usuarios-caja">
        <header className="usuarios-cabecera">
          <div>
            <h2 id="permisos-titulo">Permisos de «{dashboard.nombre}»</h2>
            <p className="modal-texto">
              Cada miembro tiene el rol de la carpeta «{dashboard.carpetaNombre}». Aquí puedes cambiarlo solo para este
              dashboard. Para agregar o quitar personas, usa «Compartir» en la carpeta.
            </p>
          </div>
          <button type="button" className="modal-cerrar usuarios-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
        </header>

        {aviso.texto && <p className={aviso.error ? 'form-error' : 'usuarios-ok'} role="status">{aviso.texto}</p>}
        {!miembros && !aviso.error && <p className="modal-texto">Cargando…</p>}
        {miembros?.length === 0 && (
          <p className="modal-texto">La carpeta aún no tiene miembros. Compártela primero desde la biblioteca de dashboards.</p>
        )}

        {miembros?.length > 0 && (
          <div className="usuarios-tabla">
            <table>
              <thead>
                <tr><th>Persona</th><th>En la carpeta</th><th>En este dashboard</th></tr>
              </thead>
              <tbody>
                {miembros.map((m) => (
                  <tr key={m.usuario}>
                    <td><strong>{m.nombre}</strong><span>{m.usuario}</span></td>
                    <td>{ROLES[m.rolCarpeta]}</td>
                    <td>
                      <select
                        className="miembros-rol"
                        aria-label={`Rol de ${m.nombre} en este dashboard`}
                        value={m.rol}
                        disabled={guardando === m.usuario}
                        onChange={(e) => cambiar(m, e.target.value)}
                      >
                        <option value="">Igual que en la carpeta</option>
                        <option value="LECTOR">Solo lectura</option>
                        <option value="EDITOR">Puede editar</option>
                      </select>
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
