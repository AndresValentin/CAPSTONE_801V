import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { crearCarpeta, guardarDashboard, listarCarpetas } from '../lib/api.js'
import './ModalRecuperar.css'
import './ModalUsuarios.css'
import './Dashboards.css'

const NUEVA = 'nueva'

// Guarda los gráficos del reporte como un dashboard en una carpeta compartida.
// Solo se guardan los planes: quien lo abra verá datos al día y solo de sus áreas.
export default function ModalGuardarDashboard({ nombreInicial, graficos, onCerrar, onSesionExpirada }) {
  const ref = useRef(null)
  const navigate = useNavigate()
  const [carpetas, setCarpetas] = useState(null)
  const [datos, setDatos] = useState({ nombre: nombreInicial.slice(0, 100), descripcion: '', carpeta: '', nuevaCarpeta: '' })
  const [estado, setEstado] = useState({ guardando: false, error: '', guardadoId: null, omitidos: [] })
  const cambiar = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }))
  // El padre crea esta función en cada render: se guarda aparte para cargar las carpetas una sola vez
  const sesionExpirada = useRef(onSesionExpirada)
  useEffect(() => { sesionExpirada.current = onSesionExpirada })

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
    listarCarpetas()
      .then(({ carpetas: todas }) => {
        const editables = todas.filter((c) => c.rol !== 'LECTOR')
        setCarpetas(editables)
        setDatos((d) => ({ ...d, carpeta: editables[0] ? String(editables[0].id) : NUEVA }))
      })
      .catch((err) => {
        if (err.estado === 401) sesionExpirada.current?.()
        else setEstado((e) => ({ ...e, error: 'No se pudieron cargar las carpetas.' }))
      })
  }, [])

  async function guardar(e) {
    e.preventDefault()
    const nueva = datos.carpeta === NUEVA
    if (!datos.nombre.trim() || (nueva && !datos.nuevaCarpeta.trim())) {
      setEstado((s) => ({ ...s, error: nueva ? 'Escribe el nombre de la carpeta y del dashboard.' : 'Escribe un nombre para el dashboard.' }))
      return
    }
    setEstado({ guardando: true, error: '', guardadoId: null, omitidos: [] })
    try {
      const carpeta = nueva ? (await crearCarpeta({ nombre: datos.nuevaCarpeta.trim(), descripcion: '' })).id : Number(datos.carpeta)
      const { id, omitidos = [] } = await guardarDashboard({
        carpeta, nombre: datos.nombre.trim(), descripcion: datos.descripcion.trim(), graficos,
      })
      setEstado({ guardando: false, error: '', guardadoId: id, omitidos })
    } catch (err) {
      if (err.estado === 401) {
        onSesionExpirada?.()
        return
      }
      setEstado({ guardando: false, error: err.message || 'No se pudo guardar el dashboard.', guardadoId: null, omitidos: [] })
    }
  }

  return (
    <dialog
      ref={ref}
      className="modal-recuperar modal-dashboard"
      aria-labelledby="guardar-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="usuarios-caja">
        <header className="usuarios-cabecera">
          <div>
            <h2 id="guardar-titulo">Guardar como dashboard</h2>
            <p className="modal-texto">
              Se guardan los {graficos.length} gráficos con sus filtros y comparaciones. Quien lo abra verá los datos
              actualizados y solo de las áreas que puede consultar.
            </p>
          </div>
          <button type="button" className="modal-cerrar usuarios-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
        </header>

        {estado.guardadoId ? (
          <>
            <p className="usuarios-ok" role="status">Dashboard guardado. Los miembros de la carpeta ya pueden verlo.</p>
            {estado.omitidos.length > 0 && (
              <div className="form-error" role="alert">
                {estado.omitidos.length === 1 ? 'Un gráfico no se incluyó' : `${estado.omitidos.length} gráficos no se incluyeron`} porque
                ya no calzan con el catálogo actual:
                <ul>{estado.omitidos.map((o) => <li key={o.titulo}>«{o.titulo}»: {o.motivo}</li>)}</ul>
              </div>
            )}
            <div className="usuarios-acciones">
              <button type="button" className="usuarios-secundario" onClick={onCerrar}>Seguir en el chat</button>
              <button type="button" className="modal-boton" onClick={() => navigate(`/dashboards/${estado.guardadoId}`)}>Abrir dashboard</button>
            </div>
          </>
        ) : (
          <form onSubmit={guardar}>
            <label className="modal-campo">
              Nombre
              <input type="text" maxLength={100} value={datos.nombre} onChange={(e) => cambiar('nombre', e.target.value)} />
            </label>
            <label className="modal-campo">
              Descripción
              <textarea rows={2} maxLength={500} value={datos.descripcion} placeholder="Para qué sirve y quién lo usa" onChange={(e) => cambiar('descripcion', e.target.value)} />
            </label>
            <label className="modal-campo">
              Carpeta
              <select value={datos.carpeta} disabled={!carpetas} onChange={(e) => cambiar('carpeta', e.target.value)}>
                {(carpetas ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}{c.rol === 'EDITOR' ? ` (de ${c.propietario})` : ''}</option>
                ))}
                <option value={NUEVA}>+ Nueva carpeta…</option>
              </select>
            </label>
            {datos.carpeta === NUEVA && (
              <label className="modal-campo">
                Nombre de la carpeta nueva
                <input type="text" maxLength={100} value={datos.nuevaCarpeta} placeholder="Ej: Comité de siniestros" onChange={(e) => cambiar('nuevaCarpeta', e.target.value)} />
              </label>
            )}
            {estado.error && <p className="form-error" role="alert">{estado.error}</p>}
            <div className="usuarios-acciones">
              <button type="button" className="usuarios-secundario" onClick={onCerrar}>Cancelar</button>
              <button type="submit" className="modal-boton" disabled={estado.guardando || !carpetas}>
                {estado.guardando ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </form>
        )}
      </div>
    </dialog>
  )
}
