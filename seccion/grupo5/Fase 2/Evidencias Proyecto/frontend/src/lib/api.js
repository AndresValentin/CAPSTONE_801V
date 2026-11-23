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
    console.error(`[api] ${ruta} respondió ${res.status}:`, detail)
    throw new ErrorApi(res.status, mensajeDeError(res.status, detail))
  }
  return res.json()
}

// El backend explica sus errores en `detail` (texto). Un 422 de FastAPI trae una lista
// técnica de campos: a la pantalla va un mensaje entendible y el detalle queda en la consola.
function mensajeDeError(estado, detail) {
  if (typeof detail === 'string' && detail) return detail
  if (estado === 422) return 'Algún dato no tiene el formato o el largo permitido. Revísalo e intenta de nuevo.'
  if (estado === 404) return 'No se encontró lo que buscabas, o no tienes acceso.'
  if (estado >= 500) return 'El servidor tuvo un problema. Intenta nuevamente en unos minutos.'
  return 'No se pudo completar la acción.'
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

// Carpetas compartidas y dashboards guardados en el servidor.
// Roles en una carpeta: PROPIETARIO, EDITOR o LECTOR; el backend los exige en cada llamada.
export function listarCarpetas() {
  return llamar('/api/carpetas', undefined, tokenActual())
}

export function crearCarpeta(datos) {
  return llamar('/api/carpetas', datos, tokenActual())
}

export function editarCarpeta(id, datos) {
  return llamar(`/api/carpetas/${id}`, datos, tokenActual())
}

export function eliminarCarpeta(id) {
  return llamar(`/api/carpetas/${id}/eliminar`, {}, tokenActual())
}

export function listarMiembros(id) {
  return llamar(`/api/carpetas/${id}/miembros`, undefined, tokenActual())
}

// rol '' quita al miembro
export function guardarMiembro(id, usuario, rol) {
  return llamar(`/api/carpetas/${id}/miembros`, { usuario, rol }, tokenActual())
}

export function directorioUsuarios() {
  return llamar('/api/usuarios-directorio', undefined, tokenActual())
}

// `graficos` = [{ titulo, plan }]
export function guardarDashboard(datos) {
  return llamar('/api/dashboards', datos, tokenActual())
}

// Vuelve a ejecutar cada gráfico con los permisos de quien lo abre
export function abrirDashboard(id) {
  return llamar(`/api/dashboards/${id}`, undefined, tokenActual())
}

// `version` evita pisar cambios de otro editor (409 si alguien guardó antes)
export function actualizarDashboard(id, datos) {
  return llamar(`/api/dashboards/${id}`, datos, tokenActual())
}

export function eliminarDashboard(id) {
  return llamar(`/api/dashboards/${id}/eliminar`, {}, tokenActual())
}

// Excepciones por dashboard (solo el propietario de la carpeta). rol '' = el de la carpeta
export function listarPermisosDashboard(id) {
  return llamar(`/api/dashboards/${id}/permisos`, undefined, tokenActual())
}

export function guardarPermisoDashboard(id, usuario, rol) {
  return llamar(`/api/dashboards/${id}/permisos`, { usuario, rol }, tokenActual())
}

// Módulo de proyecciones: series que se pueden proyectar y el cálculo de una
export function listarProyecciones() {
  return llamar('/api/proyecciones', undefined, tokenActual())
}

export function calcularProyeccion(dominio, metrica) {
  return llamar('/api/proyecciones', { dominio, metrica }, tokenActual())
}

// Dashboard completo recomendado de un área para un mes (AAAA-MM; '' = último mes completo).
// Devuelve { estado: 'dashboard', titulo, explicacion, graficos: [{ titulo, lectura, plan, interpretacion, resultado }] }
export function armarDashboardRecomendado(dominio, mes) {
  return llamar('/api/paquetes', { dominio, mes }, tokenActual())
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

// Descarga el reporte. `formato` = 'html'; `graficos` = [{ titulo, plan }].
const EXPORTACIONES = {
  html: { ruta: '/api/reporte-html', archivo: 'Reporte_RootSmart.html' },
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
    throw new ErrorApi(res.status, typeof detail === 'string' && detail ? detail : 'No se pudo generar el archivo.')
  }
  const url = URL.createObjectURL(await res.blob())
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = archivo
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
  // Gráficos que el backend dejó fuera porque ya no calzan con el catálogo
  return { omitidos: Number(res.headers.get('X-Graficos-Omitidos')) || 0 }
}
