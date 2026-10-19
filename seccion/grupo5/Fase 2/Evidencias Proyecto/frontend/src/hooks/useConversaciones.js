import { useEffect, useState } from 'react'
import { guardarLocal, leerLocal, nuevoId } from '../lib/persistencia.js'

const CLAVE_BASE = 'bi-copilot:conversaciones'
const TITULO_NUEVO = 'Nuevo chat'

function crearConversacion() {
  const ahora = new Date().toISOString()
  return { id: nuevoId(), titulo: TITULO_NUEVO, creada: ahora, actualizada: ahora, mensajes: [] }
}

function cargarConversaciones(clave) {
  const guardadas = leerLocal(clave, [])
  return Array.isArray(guardadas) && guardadas.length ? guardadas : [crearConversacion()]
}

function tituloDesde(texto) {
  return texto.length > 40 ? `${texto.slice(0, 40).trim()}…` : texto
}

// Reportes de una conversación = respuestas del asistente que generaron dashboard
export function reportesDe(conversacion) {
  return conversacion.mensajes.filter((m) => m.tipo === 'validado')
}

// Historial de chats con IA (RF-08). Hoy vive en localStorage; cuando exista
// backend, cargar/guardar se reemplazan por GET/POST a /api/conversaciones.
// `usuario` separa el historial: en un mismo navegador, cada usuario ve solo sus
// chats (que incluyen datos de sus dominios). Sin backend se usa un historial común.
export function useConversaciones(usuario) {
  const clave = usuario ? `${CLAVE_BASE}:${usuario}` : CLAVE_BASE
  const [conversaciones, setConversaciones] = useState(() => cargarConversaciones(clave))
  const [activaId, setActivaId] = useState(() => conversaciones[0].id)

  useEffect(() => { guardarLocal(clave, conversaciones) }, [clave, conversaciones])

  const activa = conversaciones.find((c) => c.id === activaId) ?? conversaciones[0]

  function agregarMensaje(conversacionId, mensaje) {
    const completo = { id: nuevoId(), fecha: new Date().toISOString(), ...mensaje }
    setConversaciones((prev) => prev.map((c) => {
      if (c.id !== conversacionId) return c
      const titulo = c.titulo === TITULO_NUEVO && mensaje.rol === 'usuario'
        ? tituloDesde(mensaje.texto)
        : c.titulo
      return { ...c, titulo, actualizada: completo.fecha, mensajes: [...c.mensajes, completo] }
    }))
    return completo
  }

  // Para reportes cuyos filtros se cambiaron en el panel: el chat guarda la última versión
  function actualizarMensaje(conversacionId, mensajeId, cambios) {
    setConversaciones((prev) => prev.map((c) => (c.id !== conversacionId ? c : {
      ...c,
      mensajes: c.mensajes.map((m) => (m.id === mensajeId ? { ...m, ...cambios } : m)),
    })))
  }

  function nuevaConversacion() {
    // Igual que en Claude: si el chat actual está vacío no se crea otro
    if (activa.mensajes.length === 0) return activa
    const nueva = crearConversacion()
    setConversaciones((prev) => [nueva, ...prev])
    setActivaId(nueva.id)
    return nueva
  }

  function eliminarConversacion(id) {
    const restantes = conversaciones.filter((c) => c.id !== id)
    const lista = restantes.length ? restantes : [crearConversacion()]
    setConversaciones(lista)
    if (id === activa.id) setActivaId(lista[0].id)
  }

  const ordenadas = [...conversaciones].sort((a, b) => b.actualizada.localeCompare(a.actualizada))

  return {
    conversaciones: ordenadas,
    activa,
    seleccionar: setActivaId,
    agregarMensaje,
    actualizarMensaje,
    nuevaConversacion,
    eliminarConversacion,
  }
}
