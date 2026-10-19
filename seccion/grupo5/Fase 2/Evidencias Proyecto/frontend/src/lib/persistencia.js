// Persistencia local mientras no exista backend: el historial de chats y los
// registros importados sobreviven a una recarga de la página.

export function nuevoId() {
  // crypto.randomUUID solo existe en contextos seguros (https o localhost)
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export function leerLocal(clave, valorPorDefecto) {
  try {
    const guardado = localStorage.getItem(clave)
    return guardado ? JSON.parse(guardado) : valorPorDefecto
  } catch {
    return valorPorDefecto
  }
}

export function guardarLocal(clave, valor) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    // Storage lleno o bloqueado (modo privado): se sigue funcionando en memoria
  }
}
