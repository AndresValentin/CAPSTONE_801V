import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileDown, MapPin, MessagesSquare, ShieldCheck, Sparkles } from 'lucide-react'
import ModalRecuperar from '../components/ModalRecuperar.jsx'
import { iniciarSesion, usaBackend } from '../lib/api.js'
import './Login.css'

// Ejemplo ilustrativo del panel de presentación
const DEMO_BARRAS = [
  { nombre: 'Hogar', valor: '$4.405 M', ancho: 100 },
  { nombre: 'Automóvil', valor: '$3.427 M', ancho: 78 },
  { nombre: 'Pyme', valor: '$2.801 M', ancho: 64 },
  { nombre: 'Empresa', valor: '$2.276 M', ancho: 52 },
]

const BENEFICIOS = [
  { icono: MessagesSquare, titulo: 'Sin escribir SQL', texto: 'Pregunta como hablas' },
  { icono: MapPin, titulo: 'Visión por región', texto: 'Gráficos y mapa de Chile' },
  { icono: FileDown, titulo: 'Listo para compartir', texto: 'Power BI o HTML interactivo' },
]

// `recuperar` = se llegó por /recuperar; el enlace del correo trae #token=...
export default function Login({ recuperar = false }) {
  const navigate = useNavigate()
  const [modal, setModal] = useState(recuperar ? 'recuperar' : null) // 'recuperar' | 'acceso' | null
  const [token, setToken] = useState(() => (
    recuperar ? new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '' : ''
  ))

  // El token no debe quedar a la vista ni en el historial del navegador
  useEffect(() => {
    if (recuperar && window.location.hash) window.history.replaceState(null, '', window.location.pathname)
  }, [recuperar])

  function cerrarModal() {
    setModal(null)
    setToken('')
    if (recuperar) navigate('/', { replace: true })
  }

  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [entrando, setEntrando] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!usuario.trim() || !password) {
      setError('Ingresa tu usuario y contraseña.')
      return
    }
    setError('')
    // En modo demo (sin backend) cualquier usuario entra
    if (!usaBackend) {
      navigate('/dashboard')
      return
    }
    // Se valida contra seguridad.SEG_USUARIO, que también define qué dominios puede consultar.
    // Al usuario solo se le muestra un mensaje simple; el detalle queda en la consola.
    setEntrando(true)
    try {
      await iniciarSesion(usuario.trim().toUpperCase(), password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.estado === 401
        ? 'Usuario o contraseña incorrectos.'
        : 'No se pudo iniciar sesión. Intenta nuevamente en unos minutos.')
    } finally {
      setEntrando(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="login-panel">
        <div className="login-panel-inner">
          <div className="brand">
            <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
            <span className="brand-name">BI Copilot</span>
          </div>

          <h1>Bienvenido de vuelta</h1>
          <p className="subtitle">
            Inicia sesión para consultar tus datos en lenguaje natural, con validaciones
            controladas y trazabilidad completa.
          </p>

          <form className="login-form" onSubmit={handleSubmit}>
            <label>
              Usuario
              <input
                type="text"
                placeholder="Ej: USR_SIN"
                autoComplete="username"
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)}
              />
            </label>

            <label>
              Contraseña
              <input
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>

            {error && <p className="form-error">{error}</p>}

            <div className="form-row">
              <label className="remember">
                <input type="checkbox" />
                Recordarme
              </label>
              {usaBackend
                ? <button type="button" className="forgot" onClick={() => setModal('recuperar')}>¿Olvidaste tu contraseña?</button>
                : <a href="#!" className="forgot">¿Olvidaste tu contraseña?</a>}
            </div>

            <button type="submit" className="btn-primary" disabled={entrando}>
              {entrando ? 'Validando…' : 'Iniciar sesión'}
            </button>
          </form>

          <p className="signup-hint">
            ¿No tienes cuenta?{' '}
            {usaBackend
              ? <button type="button" className="forgot" onClick={() => setModal('acceso')}>Solicita acceso al equipo BI</button>
              : <a href="#!">Solicita acceso al equipo BI</a>}
          </p>
        </div>
      </div>

      <div className="login-visual">
        <div className="visual-glow" />
        <div className="visual-content">
          <div className="visual-badge"><Sparkles size={13} /> Inteligencia de negocios con IA</div>
          <h2>Pregunta en español.<br />Decide con datos.</h2>
          <p>
            BI Copilot convierte tus preguntas en gráficos, mapas y reportes
            listos para presentar, en segundos.
          </p>

          <div className="demo" aria-hidden="true">
            <div className="demo-pregunta">¿Cuánto pagamos en siniestros por producto?</div>
            <div className="demo-respuesta">
              <div className="demo-cabecera">
                <div>
                  <span className="demo-etiqueta">Monto pagado</span>
                  <strong className="demo-total">$12.908 M</strong>
                </div>
                <span className="demo-area">Siniestros</span>
              </div>
              {DEMO_BARRAS.map((b, i) => (
                <div key={b.nombre} className="demo-fila">
                  <span>{b.nombre}</span>
                  <span className="demo-pista">
                    <span className="demo-barra" style={{ width: `${b.ancho}%`, animationDelay: `${0.25 + i * 0.08}s` }} />
                  </span>
                  <span className="demo-valor">{b.valor}</span>
                </div>
              ))}
            </div>
          </div>

          <ul className="visual-beneficios">
            {BENEFICIOS.map(({ icono: Icono, titulo, texto }) => (
              <li key={titulo}>
                <Icono size={18} />
                <strong>{titulo}</strong>
                <span>{texto}</span>
              </li>
            ))}
          </ul>

          <p className="visual-confianza">
            <ShieldCheck size={15} /> Solo lectura · Permisos por área · Cada consulta queda registrada
          </p>
        </div>
      </div>

      {modal && <ModalRecuperar key={modal} modo={modal} token={token} onCerrar={cerrarModal} />}
    </div>
  )
}
