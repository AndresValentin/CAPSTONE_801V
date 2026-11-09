import { interpretarSolicitud } from './copilot.js'

const API_URL = import.meta.env.VITE_API_URL
const CLAVE_SESION = 'bi-copilot:sesion'

// Sin VITE_API_URL el copiloto corre en el navegador con reglas locales (modo demo).
// Con VITE_API_URL (ej: http://localhost:8000 en un archivo .env.local) las
// preguntas van al backend Python, que usa la IA y la base de datos real.
export const usaBackend = Boolean(API_URL)

// Error de la API: `estado` es el código HTTP (0 si no hubo conexión).
// El detalle técnico va a la consola; la pantalla decide qué mostrar.
export class ErrorApi extends Error {
  constructor(estado, detalle) {
    super(detalle)
    this.estado = estado
  }
}

// cuerpo === undefined hace un GET
async function llamar(ruta, cuerpo, token) {
  let res
  try {
    res = await fetch(`${API_URL}${ruta}`, {
      method: cuerpo === undefined ? 'GET' : 'POST',
      headers: {
        ...(cuerpo === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(cuerpo === undefined ? {} : { body: JSON.stringify(cuerpo) }),
    })
  } catch (err) {
    console.error(`[api] No se pudo conectar con el backend (${API_URL}${ruta}).`, err)
    throw new ErrorApi(0, 'Sin conexión con el backend')
  }
  if (!res.ok) {
    if (res.status === 401 && token) cerrarSesion()
    const { detail } = await res.json().catch(() => ({}))
    const detalle = typeof detail === 'string' ? detail : JSON.stringify(detail)
    console.error(`[api] ${ruta} respondió ${res.status}:`, detalle)
    throw new ErrorApi(res.status, detalle)
  }
  return res.json()
}

// La sesión dura lo que la pestaña: { token, usuario, nombre, dominios: [{ codigo, nombre }] }.
// El token lo firma el backend; la contraseña nunca se guarda en el navegador.
export function leerSesion() {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE_SESION))
  } catch {
    return null
  }
}

export async function iniciarSesion(usuario, clave) {
  const sesion = await llamar('/api/sesion', { usuario, clave })
  try {
    sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion))
  } catch {
    // sin sessionStorage la sesión no sobrevive a una recarga, pero funciona
  }
  return sesion
}

// La respuesta no revela si la cuenta existe
export function solicitarRecuperacion(usuario) {
  return llamar('/api/clave/solicitar', { usuario })
}

export function restablecerClave(token, clave) {
  return llamar('/api/clave/restablecer', { token, clave })
}

export function cerrarSesion() {
  try {
    sessionStorage.removeItem(CLAVE_SESION)
  } catch {
    // nada que limpiar
  }
}

function tokenActual() {
  const sesion = leerSesion()
  if (!sesion) throw new ErrorApi(401, 'No hay sesión activa')
  return sesion.token
}

// Ambos caminos devuelven { estado, motivo?, interpretacion?, resultado?, plan? }.
// Solo el backend trae `resultado` (los datos ya calculados en SQL Server) y `plan`.
// `panel` = { filtros: { campo: valor }, desde, hasta }: filtros elegidos en el dashboard.
export async function interpretar(pregunta, panel) {
  if (!usaBackend) return interpretarSolicitud(pregunta)
  return llamar('/api/consultas', { pregunta, panel }, tokenActual())
}

// Filtros disponibles para el usuario, con los valores reales de la BD
export function obtenerCatalogo() {
  return llamar('/api/catalogo', undefined, tokenActual())
}

// Vuelve a ejecutar un reporte con otros filtros; no pasa por la IA
export function reejecutarReporte(pregunta, plan) {
  return llamar('/api/reportes', { pregunta, plan }, tokenActual())
}

export function obtenerPerfil() {
  return llamar('/api/perfil', undefined, tokenActual())
}

// Administración: el backend exige superadministrador en cada una
export function listarUsuarios() {
  return llamar('/api/usuarios', undefined, tokenActual())
}

export function crearUsuario(datos) {
  return llamar('/api/usuarios', datos, tokenActual())
}

export function actualizarUsuario(usuario, datos) {
  return llamar(`/api/usuarios/${encodeURIComponent(usuario)}`, datos, tokenActual())
}

export function enviarEnlaceClave(usuario) {
  return llamar(`/api/usuarios/${encodeURIComponent(usuario)}/enlace-clave`, {}, tokenActual())
}

// Formulario público del inicio de sesión
export function obtenerAreas() {
  return llamar('/api/areas')
}

export function enviarSolicitudAcceso(datos) {
  return llamar('/api/solicitudes-acceso', datos)
}

export function listarSolicitudes() {
  return llamar('/api/solicitudes-acceso', undefined, tokenActual())
}

export function aprobarSolicitud(id, datos) {
  return llamar(`/api/solicitudes-acceso/${id}/aprobar`, datos, tokenActual())
}

export function rechazarSolicitud(id) {
  return llamar(`/api/solicitudes-acceso/${id}/rechazar`, {}, tokenActual())
}

// Las formas de las regiones no cambian: se piden una vez por sesión
let mapaChile = null
export function obtenerMapaChile() {
  mapaChile ??= llamar('/api/mapa-chile', undefined, tokenActual()).catch((err) => {
    mapaChile = null
    throw err
  })
  return mapaChile
}

// Descarga el reporte. `formato` = 'html' o 'powerbi'; `graficos` = [{ titulo, plan }].
const EXPORTACIONES = {
  html: { ruta: '/api/reporte-html', archivo: 'Reporte_BI_Copilot.html' },
  powerbi: { ruta: '/api/powerbi', archivo: 'BI_Copilot_PowerBI.zip' },
}

export async function descargarReporte(formato, titulo, graficos) {
  const { ruta, archivo } = EXPORTACIONES[formato]
  const token = tokenActual()
  let res
  try {
    res = await fetch(`${API_URL}${ruta}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ titulo, graficos }),
    })
  } catch (err) {
    console.error(`[api] No se pudo conectar con el backend (${ruta}).`, err)
    throw new ErrorApi(0, 'Sin conexión con el backend')
  }
  if (!res.ok) {
    if (res.status === 401) cerrarSesion()
    const { detail } = await res.json().catch(() => ({}))
    throw new ErrorApi(res.status, typeof detail === 'string' ? detail : 'No se pudo generar el archivo.')
  }
  const url = URL.createObjectURL(await res.blob())
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = archivo
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}
