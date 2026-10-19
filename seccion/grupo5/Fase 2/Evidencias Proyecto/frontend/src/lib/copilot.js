import { productos, regiones, estados, catalogo, completarReporte, VISUALIZACIONES } from '../data/mockData.js'

// Verbos que inducen escritura, en SQL y en español (RN-02)
const OPERACION_ESCRITURA = /\b(insert|update|delete|drop|alter|create|exec|truncate|elimina|eliminar|borra|borrar|modifica|modificar|actualiza|actualizar|inserta|insertar)\b/

// Campo no catalogado a propósito, para demostrar RF-03 / RF-07 (CA-03)
const CAMPO_NO_AUTORIZADO = /\b(correo|email|rut|telefono|tarjeta)\b/

const DIMENSION_TEXTO = [
  ['region', /\bpor regi(o|ó)n(es)?\b/],
  ['producto', /\bpor productos?\b/],
  ['estado', /\bpor estados?\b/],
  ['mes', /\b(por mes(es)?|mensual|evolucion|tendencia)\b/],
]

const VISUALIZACION_TEXTO = [
  ['lineas', /\b(lineas?|evolucion|tendencia)\b/],
  ['torta', /\b(torta|circular|dona|distribucion)\b/],
  ['tabla', /\b(tabla|listado|detalle)\b/],
  ['kpi', /\b(kpi|indicador)\b/],
  ['barras', /\b(barras?|compara\w*)\b/],
]

export const PREGUNTA_ACLARACION = 'Necesito un poco más de información para armar el reporte. Indícame:\n'
  + '1. Qué quieres medir: monto pagado total, cantidad de siniestros o monto promedio.\n'
  + '2. Filtros: producto, región, estado o período (AAAA-MM).\n'
  + '3. Cómo verlo: barras, líneas, torta, KPI o tabla.'

function sinTildes(texto) {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

function encontrarCoincidencia(texto, opciones) {
  return opciones.find((op) => texto.includes(sinTildes(op)))
}

function detectar(texto, patrones) {
  return patrones.find(([, regex]) => regex.test(texto))?.[0]
}

function detectarMetrica(texto) {
  if (/promedio/.test(texto)) return 'monto_promedio'
  if (/cantidad|cuantos|numero de/.test(texto)) return 'cantidad_siniestros'
  if (/monto|pagad|total/.test(texto)) return 'monto_pagado_total'
  return undefined
}

// Interpreta una solicitud en lenguaje natural y la valida contra el catálogo
// autorizado, simulando el flujo RF-01 a RF-04 y RF-07 de la EF.
// Devuelve estado: 'validado' | 'rechazado' | 'aclaracion'.
export function interpretarSolicitud(texto) {
  const textoNorm = sinTildes(texto.trim())

  if (!textoNorm) {
    return { estado: 'rechazado', motivo: 'La solicitud no puede estar vacía.' }
  }

  if (OPERACION_ESCRITURA.test(textoNorm)) {
    return {
      estado: 'rechazado',
      motivo: 'RN-02: la solicitud parece inducir una operación de escritura. Solo se permiten consultas de lectura.',
    }
  }

  if (CAMPO_NO_AUTORIZADO.test(textoNorm)) {
    return {
      estado: 'rechazado',
      motivo: 'RF-03: la solicitud referencia un campo que no existe en el catálogo autorizado del dominio "Siniestros".',
    }
  }

  // "monto pagado" es la métrica, no el estado "Pagado"
  const textoSinMetrica = textoNorm.replace(/montos? pagados?/g, '')
  const meses = (textoNorm.match(/\b20\d{2}-(0[1-9]|1[0-2])\b/g) ?? []).sort()

  const metrica = detectarMetrica(textoNorm)
  const agruparPor = detectar(textoNorm, DIMENSION_TEXTO)
  const visualizacion = detectar(textoNorm, VISUALIZACION_TEXTO)
  const filtros = {
    producto: encontrarCoincidencia(textoNorm, productos),
    region: encontrarCoincidencia(textoNorm, regiones),
    estado: encontrarCoincidencia(textoSinMetrica, estados),
    desde: meses[0],
    hasta: meses.at(-1),
  }

  const entendioAlgo = metrica || agruparPor || visualizacion || Object.values(filtros).some(Boolean)
  if (!entendioAlgo) {
    return { estado: 'aclaracion', motivo: PREGUNTA_ACLARACION }
  }

  const reporte = completarReporte({ metrica, agruparPor, visualizacion })

  return {
    estado: 'validado',
    interpretacion: {
      intencion: 'Análisis agregado de siniestros',
      dominio: catalogo.dominio,
      ...reporte,
      filtros,
      tipoSalida: VISUALIZACIONES[reporte.visualizacion],
      catalogoVersion: catalogo.version,
    },
  }
}
