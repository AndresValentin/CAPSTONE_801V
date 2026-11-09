import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, MailCheck, Sparkles, X } from 'lucide-react'
import { enviarSolicitudAcceso, obtenerAreas, restablecerClave, solicitarRecuperacion } from '../lib/api.js'
import './ModalRecuperar.css'

const LARGO_MINIMO = 8

function Mensaje({ icono: Icono, titulo, texto, boton, onClick }) {
  return (
    <div className="modal-mensaje">
      <span className="modal-icono"><Icono size={26} /></span>
      <h2 id="modal-titulo">{titulo}</h2>
      <p className="modal-texto">{texto}</p>
      <button type="button" className="modal-boton" autoFocus onClick={onClick}>{boton}</button>
    </div>
  )
}

function Solicitar({ onCerrar }) {
  const [usuario, setUsuario] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  async function enviar(e) {
    e.preventDefault()
    if (!usuario.trim()) {
      setError('Ingresa tu usuario.')
      return
    }
    setError('')
    setEnviando(true)
    try {
      await solicitarRecuperacion(usuario.trim())
      setEnviado(true)
    } catch {
      setError('No se pudo procesar la solicitud. Intenta nuevamente en unos minutos.')
    } finally {
      setEnviando(false)
    }
  }

  if (enviado) {
    return (
      <Mensaje
        icono={MailCheck}
        titulo="Revisa tu correo"
        texto="Si la cuenta existe y tiene un correo registrado, te enviamos un enlace para cambiar tu contraseña. Vence en 30 minutos; revisa también la carpeta de spam."
        boton="Entendido"
        onClick={onCerrar}
      />
    )
  }

  return (
    <form className="modal-form" onSubmit={enviar}>
      <div>
        <h2 id="modal-titulo">Encuentra tu cuenta</h2>
        <p className="modal-texto">Ingresa tu usuario y te enviaremos un enlace al correo registrado.</p>
        <label className="modal-campo">
          Usuario
          <input type="text" autoComplete="username" placeholder="Ej: USR_SIN" value={usuario} onChange={(e) => setUsuario(e.target.value)} />
        </label>
        {error && <p className="form-error modal-error" role="alert">{error}</p>}
      </div>
      <button type="submit" className="modal-boton" disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar enlace'}</button>
    </form>
  )
}

function SolicitarAcceso({ onCerrar }) {
  const [datos, setDatos] = useState({ nombre: '', correo: '', motivo: '', sitio: '' })
  const [areas, setAreas] = useState([])
  const [elegidas, setElegidas] = useState([])
  const [enviado, setEnviado] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const cambiar = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }))

  useEffect(() => {
    obtenerAreas().then(setAreas).catch(() => {}) // sin la lista igual se puede enviar la solicitud
  }, [])

  function alternar(codigo) {
    setElegidas((l) => (l.includes(codigo) ? l.filter((c) => c !== codigo) : [...l, codigo]))
  }

  async function enviar(e) {
    e.preventDefault()
    if (!datos.nombre.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(datos.correo.trim())) {
      setError('Ingresa tu nombre y un correo válido.')
      return
    }
    setError('')
    setEnviando(true)
    try {
      await enviarSolicitudAcceso({ ...datos, correo: datos.correo.trim(), areas: elegidas })
      setEnviado(true)
    } catch {
      setError('No se pudo enviar la solicitud. Intenta nuevamente en unos minutos.')
    } finally {
      setEnviando(false)
    }
  }

  if (enviado) {
    return (
      <Mensaje
        icono={CheckCircle2}
        titulo="Solicitud recibida"
        texto="El equipo BI la revisará. Si se aprueba, te llegará un correo para crear tu contraseña."
        boton="Entendido"
        onClick={onCerrar}
      />
    )
  }

  return (
    <form className="modal-form" onSubmit={enviar}>
      <div>
        <h2 id="modal-titulo">Solicita acceso</h2>
        <p className="modal-texto">Cuéntanos quién eres y qué necesitas consultar.</p>
        <label className="modal-campo">
          Nombre
          <input type="text" autoComplete="name" maxLength={100} value={datos.nombre} onChange={(e) => cambiar('nombre', e.target.value)} />
        </label>
        <label className="modal-campo">
          Correo
          <input type="email" autoComplete="email" maxLength={254} value={datos.correo} onChange={(e) => cambiar('correo', e.target.value)} />
        </label>
        {areas.length > 0 && (
          <fieldset className="modal-areas">
            <legend>Áreas que necesitas</legend>
            {areas.map((a) => (
              <label key={a.codigo}>
                <input type="checkbox" checked={elegidas.includes(a.codigo)} onChange={() => alternar(a.codigo)} /> {a.nombre}
              </label>
            ))}
          </fieldset>
        )}
        <label className="modal-campo">
          Motivo (opcional)
          <textarea rows={2} maxLength={500} value={datos.motivo} onChange={(e) => cambiar('motivo', e.target.value)} />
        </label>
        <input className="modal-trampa" type="text" tabIndex={-1} autoComplete="off" aria-hidden="true" value={datos.sitio} onChange={(e) => cambiar('sitio', e.target.value)} />
        {error && <p className="form-error modal-error" role="alert">{error}</p>}
      </div>
      <button type="submit" className="modal-boton" disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar solicitud'}</button>
    </form>
  )
}

function Restablecer({ token, onCerrar }) {
  const [clave, setClave] = useState('')
  const [repetida, setRepetida] = useState('')
  const [listo, setListo] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar(e) {
    e.preventDefault()
    if (clave.length < LARGO_MINIMO) {
      setError(`La contraseña debe tener al menos ${LARGO_MINIMO} caracteres.`)
      return
    }
    if (clave !== repetida) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setError('')
    setGuardando(true)
    try {
      await restablecerClave(token, clave)
      setListo(true)
    } catch (err) {
      setError(err.estado === 400 ? err.message : 'No se pudo cambiar la contraseña. Intenta nuevamente en unos minutos.')
    } finally {
      setGuardando(false)
    }
  }

  if (listo) {
    return <Mensaje icono={CheckCircle2} titulo="Contraseña actualizada" texto="Ya puedes iniciar sesión con tu contraseña nueva." boton="Iniciar sesión" onClick={onCerrar} />
  }

  return (
    <form className="modal-form" onSubmit={guardar}>
      <div>
        <h2 id="modal-titulo">Crea tu contraseña nueva</h2>
        <p className="modal-texto">Debe tener al menos {LARGO_MINIMO} caracteres.</p>
        <label className="modal-campo">
          Contraseña nueva
          <input type="password" autoComplete="new-password" value={clave} onChange={(e) => setClave(e.target.value)} />
        </label>
        <label className="modal-campo">
          Repite la contraseña
          <input type="password" autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} />
        </label>
        {error && <p className="form-error modal-error" role="alert">{error}</p>}
      </div>
      <button type="submit" className="modal-boton" disabled={guardando}>{guardando ? 'Guardando…' : 'Cambiar contraseña'}</button>
    </form>
  )
}

// Ventana sobre el login. Con `token` (enlace del correo) pide la contraseña nueva.
// <dialog> ya resuelve el fondo, la tecla Esc y mantener el foco dentro.
export default function ModalRecuperar({ modo = 'recuperar', token, onCerrar }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo.open) dialogo.showModal()
    dialogo.querySelector('input')?.focus()
  }, [])

  return (
    <dialog
      ref={ref}
      className="modal-recuperar"
      aria-labelledby="modal-titulo"
      onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}
    >
      <div className="modal-caja">
        <header className="modal-cabecera">
          <button type="button" className="modal-cerrar" aria-label="Cerrar" onClick={onCerrar}><X size={19} /></button>
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
        </header>
        <div className="modal-cuerpo">
          {modo === 'acceso'
            ? <SolicitarAcceso onCerrar={onCerrar} />
            : token ? <Restablecer token={token} onCerrar={onCerrar} /> : <Solicitar onCerrar={onCerrar} />}
        </div>
      </div>
    </dialog>
  )
}
