import { productos, regiones, estados, catalogo } from '../data/mockData.js'

const PALABRAS_BLOQUEADAS = ['insert', 'update', 'delete', 'drop', 'alter', 'create', 'exec', 'truncate']

function encontrarCoincidencia(texto, opciones) {
  const textoLower = texto.toLowerCase()
  return opciones.find((op) => textoLower.includes(op.toLowerCase()))
}

// Interpreta una solicitud en lenguaje natural y la valida contra el catálogo
// autorizado, simulando el flujo RF-01 a RF-04 y RF-07 de la EF.
export function interpretarSolicitud(texto) {
  const textoLower = texto.trim().toLowerCase()

  if (!texto.trim()) {
    return {
      estado: 'rechazado',
      motivo: 'La solicitud no puede estar vacía.',
    }
  }

  const contieneOperacionEscritura = PALABRAS_BLOQUEADAS.some((p) => textoLower.includes(p))
  if (contieneOperacionEscritura) {
    return {
      estado: 'rechazado',
      motivo: 'RN-02: la solicitud parece inducir una operación de escritura. Solo se permiten consultas de lectura.',
    }
  }

  const producto = encontrarCoincidencia(texto, productos)
  const region = encontrarCoincidencia(texto, regiones)
  const estado = encontrarCoincidencia(texto, estados)

  const pideMonto = /monto|pagad|total/.test(textoLower)
  const pideCantidad = /cantidad|cuántos|cuantos|número de|numero de/.test(textoLower)

  const metrica = pideMonto ? 'monto_pagado_total' : pideCantidad ? 'cantidad_siniestros' : 'cantidad_siniestros'

  // Campo no catalogado a propósito, para demostrar RF-03 / RF-07 (CA-03)
  const campoNoAutorizado = /correo|email|rut|teléfono|telefono|tarjeta/.test(textoLower)
  if (campoNoAutorizado) {
    return {
      estado: 'rechazado',
      motivo: 'RF-03: la solicitud referencia un campo que no existe en el catálogo autorizado del dominio "Siniestros".',
    }
  }

  const filtros = { producto, region, estado }
  const tipoSalida = pideMonto || pideCantidad ? 'kpi + gráfico' : 'tabla de detalle'

  return {
    estado: 'validado',
    interpretacion: {
      intencion: 'Análisis agregado de siniestros',
      dominio: catalogo.dominio,
      metrica,
      filtros,
      tipoSalida,
      catalogoVersion: catalogo.version,
    },
  }
}
