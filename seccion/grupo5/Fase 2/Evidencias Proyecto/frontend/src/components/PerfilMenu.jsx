import { useCallback, useEffect, useRef, useState } from 'react'
import { Building2, ChevronUp, LogOut, Moon, ShieldCheck, Smartphone, Users } from 'lucide-react'
import ModalUsuarios from './ModalUsuarios.jsx'
import { obtenerPerfil } from '../lib/api.js'
import { aplicarIos, aplicarTema, iosGuardado, temaGuardado } from '../lib/tema.js'
import './PerfilMenu.css'

function iniciales(nombre) {
  return nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')
}

// Pie de la barra lateral: cuenta, organización, tema y, si corresponde, administración
export default function PerfilMenu({ sesion, onSalir }) {
  const [abierto, setAbierto] = useState(false)
  const [perfil, setPerfil] = useState(null)
  const [tema, setTema] = useState(temaGuardado)
  const [ios, setIos] = useState(iosGuardado)
  const [administrando, setAdministrando] = useState(false)
  const raiz = useRef(null)

  const cargar = useCallback(() => {
    if (!sesion) return
    obtenerPerfil().then(setPerfil).catch(() => {}) // sin perfil se muestran los datos de la sesión
  }, [sesion])

  useEffect(() => { cargar() }, [cargar])

  useEffect(() => {
    if (!abierto) return undefined
    const afuera = (e) => { if (!raiz.current?.contains(e.target)) setAbierto(false) }
    const tecla = (e) => { if (e.key === 'Escape') setAbierto(false) }
    document.addEventListener('pointerdown', afuera)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('pointerdown', afuera)
      document.removeEventListener('keydown', tecla)
    }
  }, [abierto])

  function alternarTema() {
    const nuevo = tema === 'oscuro' ? 'claro' : 'oscuro'
    setTema(nuevo)
    aplicarTema(nuevo)
  }

  function alternarIos() {
    setIos(!ios)
    aplicarIos(!ios)
  }

  const pendientes = perfil?.solicitudesPendientes ?? 0
  const nombre = perfil?.nombre ?? sesion?.nombre ?? 'Modo demo'
  const rol = perfil ? (perfil.superadmin ? 'Superadministrador' : 'Usuario') : ''
  const areas = perfil?.areas ?? sesion?.dominios.map((d) => d.nombre) ?? []

  return (
    <div className="perfil" ref={raiz}>
      {abierto && (
        <div className="perfil-menu" role="menu" aria-label="Cuenta">
          <div className="perfil-cuenta">
            <strong>{nombre}</strong>
            {perfil && <span>{perfil.usuario}</span>}
            <span>{perfil?.correo || 'Sin correo registrado'}</span>
          </div>

          {perfil && (
            <div className="perfil-seccion">
              <p><Building2 size={14} /> {perfil.organizacion}</p>
              <p><ShieldCheck size={14} /> {rol}</p>
              <div className="perfil-areas">
                {areas.map((a) => <span key={a}>{a}</span>)}
              </div>
            </div>
          )}

          <div className="perfil-seccion">
            <button type="button" role="switch" aria-checked={tema === 'oscuro'} className="perfil-opcion" onClick={alternarTema}>
              <Moon size={15} /> Modo oscuro
              <span className={`perfil-switch ${tema === 'oscuro' ? 'perfil-switch-on' : ''}`} />
            </button>
            <button type="button" role="switch" aria-checked={ios} className="perfil-opcion" onClick={alternarIos}>
              <Smartphone size={15} /> Estilo iOS
              <span className={`perfil-switch ${ios ? 'perfil-switch-on' : ''}`} />
            </button>
            {perfil?.superadmin && (
              <button type="button" className="perfil-opcion" onClick={() => { setAbierto(false); setAdministrando(true) }}>
                <Users size={15} /> Administrar usuarios
                {pendientes > 0 && <span className="perfil-contador" title="Solicitudes de acceso pendientes">{pendientes}</span>}
              </button>
            )}
            {sesion && (
              <button type="button" className="perfil-opcion" onClick={onSalir}>
                <LogOut size={15} /> Cerrar sesión
              </button>
            )}
          </div>
        </div>
      )}

      <button type="button" className="perfil-boton" aria-haspopup="menu" aria-expanded={abierto} onClick={() => setAbierto((v) => !v)}>
        <span className="perfil-avatar">
          {iniciales(nombre)}
          {pendientes > 0 && <span className="perfil-punto" aria-label={`${pendientes} solicitudes pendientes`} />}
        </span>
        <span className="perfil-texto">
          <strong>{nombre}</strong>
          <span>{rol || (perfil?.organizacion ?? 'BI Copilot')}</span>
        </span>
        <ChevronUp size={15} />
      </button>

      {administrando && (
        <ModalUsuarios
          usuarioActual={perfil.usuario}
          onCerrar={() => setAdministrando(false)}
          onCambio={cargar}
          onSesionExpirada={onSalir}
        />
      )}
    </div>
  )
}
