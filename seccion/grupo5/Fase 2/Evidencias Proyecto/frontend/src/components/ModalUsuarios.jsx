import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, Mail, Pencil, Plus, X } from 'lucide-react'
import {
  actualizarUsuario, aprobarSolicitud, crearUsuario, enviarEnlaceClave, listarSolicitudes, listarUsuarios, rechazarSolicitud,
} from '../lib/api.js'
import './ModalRecuperar.css'
import './ModalUsuarios.css'

const NUEVO = { usuario: '', nombre: '', correo: '', dominios: [], superadmin: false, activo: true }

function textoError(err, porDefecto) {
  return err.estado === 422 ? 'Revisa los datos: usuario de 3 a 50 letras, números o _, y un correo válido.' : err.message || porDefecto
}

// Propone un código de usuario a partir del correo
function usuarioSugerido(correo) {
  const base = correo.split('@')[0].toUpperCase().replace(/[^A-Z0-9_]/g, '_').slice(0, 46)
  return `USR_${base}`
}

function Formulario({ inicial, codigoEditable, esPropio, dominios, nota, onEnviar, onGuardado, onCancelar, onSesionExpirada }) {
  const [datos, setDatos] = useState(inicial)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const cambiar = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }))

  function alternarDominio(codigo) {
    cambiar('dominios', datos.dominios.includes(codigo) ? datos.dominios.filter((d) => d !== codigo) : [...datos.dominios, codigo])
  }

  async function guardar(e) {
    e.preventDefault()
    if (!datos.nombre.trim() || !datos.usuario.trim()) {
      setError('Completa el usuario y el nombre.')
      return
    }
    setError('')
    setGuardando(true)
    try {
      await onEnviar(datos)
      onGuardado()
    } catch (err) {
      if (err.estado === 401) {
        onSesionExpirada()
        return
      }
      setError(textoError(err, 'No se pudo guardar el usuario.'))
      setGuardando(false)
    }
  }

  return (
    <form className="usuarios-form" onSubmit={guardar}>
      <label className="modal-campo">
        Usuario
        <input type="text" value={datos.usuario} disabled={!codigoEditable} placeholder="Ej: USR_ANA" onChange={(e) => cambiar('usuario', e.target.value)} />
      </label>
      <label className="modal-campo">
        Nombre
        <input type="text" maxLength={100} value={datos.nombre} onChange={(e) => cambiar('nombre', e.target.value)} />
      </label>
      <label className="modal-campo usuarios-ancho">
        Correo
        <input type="email" maxLength={254} value={datos.correo} placeholder="Para recuperar la contraseña" onChange={(e) => cambiar('correo', e.target.value)} />
      </label>

      <fieldset className="usuarios-grupo usuarios-ancho">
        <legend>Áreas que puede consultar</legend>
        {dominios.map((d) => (
          <label key={d.codigo}>
            <input type="checkbox" checked={datos.dominios.includes(d.codigo)} onChange={() => alternarDominio(d.codigo)} /> {d.nombre}
          </label>
        ))}
      </fieldset>

      <fieldset className="usuarios-grupo usuarios-ancho">
        <legend>Permisos</legend>
        <label>
          <input type="checkbox" checked={datos.superadmin} disabled={esPropio} onChange={(e) => cambiar('superadmin', e.target.checked)} /> Superadministrador
        </label>
        <label>
          <input type="checkbox" checked={datos.activo} disabled={esPropio} onChange={(e) => cambiar('activo', e.target.checked)} /> Cuenta activa
        </label>
      </fieldset>

      {nota && <p className="usuarios-nota usuarios-ancho">{nota}</p>}
      {error && <p className="form-error usuarios-ancho" role="alert">{error}</p>}

      <div className="usuarios-acciones usuarios-ancho">
        <button type="button" className="usuarios-secundario" onClick={onCancelar}>Cancelar</button>
        <button type="submit" className="modal-boton" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
      </div>
    </form>
  )
}

// Solo lo abre un superadministrador; el backend vuelve a comprobarlo en cada acción
export default function ModalUsuarios({ usuarioActual, onCerrar, onCambio, onSesionExpirada }) {
  const ref = useRef(null)
  const [datos, setDatos] = useState(null)
  const [solicitudes, setSolicitudes] = useState([])
  const [pestana, setPestana] = useState('usuarios')
  const [edicion, setEdicion] = useState(null) // { titulo, inicial, codigoEditable, nota, enviar }
  const [aviso, setAviso] = useState({ texto: '', error: false })

  const fallo = useCallback((err, porDefecto) => {
    if (err.estado === 401) onSesionExpirada()
    else setAviso({ texto: textoError(err, porDefecto), error: true })
  }, [onSesionExpirada])

  const cargar = useCallback(() => Promise.all([listarUsuarios(), listarSolicitudes()])
    .then(([u, s]) => {
      setDatos(u)
      setSolicitudes(s.solicitudes)
    })
    .catch((err) => fallo(err, 'No se pudieron cargar los usuarios.')), [fallo])

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
    cargar()
  }, [cargar])

  const nombreArea = (codigo) => datos.dominios.find((d) => d.codigo === codigo)?.nombre ?? codigo
  const limpiarAviso = () => setAviso({ texto: '', error: false })

  async function enviarEnlace(u) {
    limpiarAviso()
    try {
      await enviarEnlaceClave(u.usuario)
      setAviso({ texto: `Enviamos el enlace a ${u.correo}.`, error: false })
    } catch (err) {
      fallo(err, 'No se pudo enviar el enlace.')
    }
  }

  function guardado(texto = 'Cambios guardados.') {
    setEdicion(null)
    setAviso({ texto, error: false })
    cargar()
    onCambio()
  }

  function nuevoUsuario() {
    limpiarAviso()
    setEdicion({
      titulo: 'Nuevo usuario',
      inicial: NUEVO,
      codigoEditable: true,
      nota: 'La cuenta se crea sin contraseña. Después, envíale el enlace para que defina la suya.',
      enviar: crearUsuario,
      mensaje: 'Usuario creado.',
    })
  }

  function editarUsuario(u) {
    limpiarAviso()
    setEdicion({
      titulo: `Editar ${u.usuario}`,
      inicial: u,
      codigoEditable: false,
      enviar: (d) => actualizarUsuario(d.usuario, d),
      mensaje: 'Cambios guardados.',
    })
  }

  function aprobar(s) {
    limpiarAviso()
    setEdicion({
      titulo: 'Aprobar solicitud',
      inicial: { ...NUEVO, usuario: usuarioSugerido(s.correo), nombre: s.nombre, correo: s.correo, dominios: s.areas },
      codigoEditable: true,
      nota: 'Al guardar se crea la cuenta y se envía a su correo el enlace para definir la contraseña.',
      enviar: (d) => aprobarSolicitud(s.id, d),
      mensaje: `Solicitud de ${s.nombre} aprobada.`,
    })
  }

  async function rechazar(s) {
    limpiarAviso()
    try {
      await rechazarSolicitud(s.id)
      setAviso({ texto: `Solicitud de ${s.nombre} rechazada.`, error: false })
      cargar()
      onCambio()
    } catch (err) {
      fallo(err, 'No se pudo rechazar la solicitud.')
    }
  }

  return (
    <dialog
      ref={ref}
      className="modal-recuperar modal-usuarios"
      aria-labelledby="usuarios-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="usuarios-caja">
        <header className="usuarios-cabecera">
          <div>
            <h2 id="usuarios-titulo">{edicion ? edicion.titulo : 'Usuarios'}</h2>
            {!edicion && <p className="modal-texto">Crea cuentas y define qué áreas puede consultar cada persona.</p>}
          </div>
          <button type="button" className="modal-cerrar usuarios-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
        </header>

        {!datos && !aviso.error && <p className="modal-texto">Cargando…</p>}

        {edicion && datos && (
          <Formulario
            key={edicion.titulo}
            inicial={edicion.inicial}
            codigoEditable={edicion.codigoEditable}
            esPropio={edicion.inicial.usuario === usuarioActual}
            dominios={datos.dominios}
            nota={edicion.nota}
            onEnviar={edicion.enviar}
            onGuardado={() => guardado(edicion.mensaje)}
            onCancelar={() => setEdicion(null)}
            onSesionExpirada={onSesionExpirada}
          />
        )}

        {!edicion && aviso.texto && <p className={aviso.error ? 'form-error' : 'usuarios-ok'} role="status">{aviso.texto}</p>}

        {!edicion && datos && (
          <>
            <div className="usuarios-barra">
              <div className="usuarios-pestanas" role="group" aria-label="Sección">
                <button type="button" aria-pressed={pestana === 'usuarios'} onClick={() => setPestana('usuarios')}>Usuarios</button>
                <button type="button" aria-pressed={pestana === 'solicitudes'} onClick={() => setPestana('solicitudes')}>
                  Solicitudes{solicitudes.length > 0 ? ` (${solicitudes.length})` : ''}
                </button>
              </div>
              {pestana === 'usuarios' && (
                <button type="button" className="usuarios-nuevo" onClick={nuevoUsuario}><Plus size={15} /> Nuevo usuario</button>
              )}
            </div>

            {pestana === 'usuarios' && (
              <div className="usuarios-tabla">
                <table>
                  <thead>
                    <tr><th>Usuario</th><th>Correo</th><th>Áreas</th><th>Estado</th><th /></tr>
                  </thead>
                  <tbody>
                    {datos.usuarios.map((u) => (
                      <tr key={u.usuario}>
                        <td>
                          <strong>{u.nombre}</strong>
                          <span>{u.usuario}{u.superadmin ? ' · Superadministrador' : ''}</span>
                        </td>
                        <td>{u.correo || '—'}</td>
                        <td className="usuarios-areas">{u.dominios.map(nombreArea).join(', ') || 'Ninguna'}</td>
                        <td>{u.activo ? 'Activo' : 'Inactivo'}</td>
                        <td className="usuarios-botones">
                          <button type="button" title="Enviar enlace para definir contraseña" aria-label={`Enviar enlace a ${u.usuario}`} disabled={!u.correo || !u.activo} onClick={() => enviarEnlace(u)}><Mail size={15} /></button>
                          <button type="button" title="Editar" aria-label={`Editar ${u.usuario}`} onClick={() => editarUsuario(u)}><Pencil size={15} /></button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {pestana === 'solicitudes' && solicitudes.length === 0 && (
              <p className="usuarios-vacio">No hay solicitudes pendientes.</p>
            )}

            {pestana === 'solicitudes' && solicitudes.length > 0 && (
              <div className="usuarios-tabla">
                <table>
                  <thead>
                    <tr><th>Persona</th><th>Áreas</th><th>Motivo</th><th>Fecha</th><th /></tr>
                  </thead>
                  <tbody>
                    {solicitudes.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.nombre}</strong>
                          <span>{s.correo}</span>
                        </td>
                        <td className="usuarios-areas">{s.areas.map(nombreArea).join(', ') || 'Sin indicar'}</td>
                        <td>{s.motivo || '—'}</td>
                        <td>{s.fecha}</td>
                        <td className="usuarios-botones">
                          <button type="button" title="Aprobar" aria-label={`Aprobar a ${s.nombre}`} onClick={() => aprobar(s)}><Check size={16} /></button>
                          <button type="button" title="Rechazar" aria-label={`Rechazar a ${s.nombre}`} onClick={() => rechazar(s)}><X size={16} /></button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </dialog>
  )
}
