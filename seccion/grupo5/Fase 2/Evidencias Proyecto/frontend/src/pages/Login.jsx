import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, ShieldCheck, DatabaseZap } from 'lucide-react'
import './Login.css'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!email.trim() || !password.trim()) {
      setError('Ingresa tu correo y contraseña para continuar.')
      return
    }
    setError('')
    navigate('/dashboard')
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
              Correo corporativo
              <input
                type="email"
                placeholder="nombre@empresa.cl"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>

            <label>
              Contraseña
              <input
                type="password"
                placeholder="••••••••"
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
              <a href="#!" className="forgot">¿Olvidaste tu contraseña?</a>
            </div>

            <button type="submit" className="btn-primary">Iniciar sesión</button>
          </form>

          <p className="signup-hint">
            ¿No tienes cuenta? <a href="#!">Solicita acceso al equipo BI</a>
          </p>
        </div>
      </div>

      <div className="login-visual">
        <div className="visual-glow" />
        <div className="visual-content">
          <div className="visual-badge">Capstone PTY4614 · BI + IA</div>
          <h2>Consultas de negocio, en segundos.</h2>
          <p>
            Escribe una pregunta analítica, el sistema valida el catálogo autorizado
            y devuelve un resultado presentable: KPI, tabla o gráfico.
          </p>

          <div className="visual-stats">
            <div className="stat-card">
              <ShieldCheck size={18} />
              <span className="stat-value">100%</span>
              <span className="stat-label">Consultas de solo lectura</span>
            </div>
            <div className="stat-card">
              <DatabaseZap size={18} />
              <span className="stat-value">0</span>
              <span className="stat-label">Datos reales expuestos</span>
            </div>
          </div>

          <div className="visual-shapes" aria-hidden="true">
            <span className="shape shape-1" />
            <span className="shape shape-2" />
            <span className="shape shape-3" />
          </div>
        </div>
      </div>
    </div>
  )
}
