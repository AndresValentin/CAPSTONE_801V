import { guardarLocal, leerLocal } from './persistencia.js'

const CLAVE = 'bi-copilot:tema'
const CLAVE_IOS = 'bi-copilot:estilo-ios'

export function temaGuardado() {
  return leerLocal(CLAVE, 'claro') === 'oscuro' ? 'oscuro' : 'claro'
}

export function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema === 'oscuro' ? 'dark' : 'light'
  guardarLocal(CLAVE, tema)
}

// Estilo iOS: capa opcional definida por completo en ios.css
export function iosGuardado() {
  return leerLocal(CLAVE_IOS, true) !== false
}

export function aplicarIos(activo) {
  if (activo) document.documentElement.dataset.look = 'ios'
  else delete document.documentElement.dataset.look
  guardarLocal(CLAVE_IOS, activo)
}
