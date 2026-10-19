// Datos sintéticos del dominio "Siniestros" (RN-06: sin datos reales de clientes)
// Estructura alineada al catálogo descrito en la EF: póliza, siniestro, cliente,
// fecha, producto, región, estado y montos autorizados.

export const catalogo = {
  dominio: 'Siniestros',
  version: 'catalogo-v0.3',
  tablas: ['poliza', 'siniestro', 'cliente'],
  camposAutorizados: [
    'producto', 'region', 'estado', 'fecha', 'monto_pagado', 'cantidad_siniestros',
  ],
  filtrosPermitidos: ['producto', 'region', 'estado', 'rango_fecha'],
  metricas: ['monto_pagado_total', 'cantidad_siniestros', 'monto_promedio'],
}

export const productos = ['Automotriz', 'Hogar', 'Salud', 'Vida']
export const regiones = ['Metropolitana', 'Valparaíso', 'Biobío', 'Los Lagos', 'Antofagasta']
export const estados = ['Aprobado', 'En revisión', 'Rechazado', 'Pagado']
const meses = ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03']

function seededRandom(seed) {
  let value = seed
  return () => {
    value = (value * 9301 + 49297) % 233280
    return value / 233280
  }
}

const rand = seededRandom(42)

export const siniestrosBase = Array.from({ length: 90 }).map((_, i) => {
  const producto = productos[Math.floor(rand() * productos.length)]
  const region = regiones[Math.floor(rand() * regiones.length)]
  const estado = estados[Math.floor(rand() * estados.length)]
  const fecha = meses[Math.floor(rand() * meses.length)]
  const monto = Math.round(150000 + rand() * 4500000)
  return {
    id: `SIN-${String(1000 + i)}`,
    poliza: `POL-${String(20000 + i)}`,
    clienteId: `CLI-${String(500 + Math.floor(rand() * 220))}`,
    producto,
    region,
    estado,
    fecha,
    monto,
  }
})

export const FILTROS_INICIALES = {
  producto: 'Todos',
  region: 'Todas',
  estado: 'Todos',
  desde: '',
  hasta: '',
}

// Completa los filtros que la IA no especificó con "sin filtro"
export function completarFiltros(filtros = {}) {
  return {
    producto: filtros.producto || FILTROS_INICIALES.producto,
    region: filtros.region || FILTROS_INICIALES.region,
    estado: filtros.estado || FILTROS_INICIALES.estado,
    desde: filtros.desde || '',
    hasta: filtros.hasta || '',
  }
}

export function filtrarSiniestros(data, { producto, region, estado, desde, hasta }) {
  return data.filter((s) => {
    if (producto && producto !== 'Todos' && s.producto !== producto) return false
    if (region && region !== 'Todas' && s.region !== region) return false
    if (estado && estado !== 'Todos' && s.estado !== estado) return false
    if (desde && s.fecha < desde) return false
    if (hasta && s.fecha > hasta) return false
    return true
  })
}

export function resumenPorMes(data) {
  const map = {}
  data.forEach((s) => {
    map[s.fecha] = map[s.fecha] || { fecha: s.fecha, monto: 0, cantidad: 0 }
    map[s.fecha].monto += s.monto
    map[s.fecha].cantidad += 1
  })
  return Object.values(map).sort((a, b) => a.fecha.localeCompare(b.fecha))
}

// Opciones de reporte: lo que el usuario puede pedir y cómo verlo
export const METRICAS = {
  monto_pagado_total: { etiqueta: 'Monto pagado total', moneda: true },
  cantidad_siniestros: { etiqueta: 'Cantidad de siniestros', moneda: false },
  monto_promedio: { etiqueta: 'Monto promedio', moneda: true },
}

export const DIMENSIONES = {
  ninguno: 'Sin agrupar',
  producto: 'Producto',
  region: 'Región',
  estado: 'Estado',
  mes: 'Mes',
}

export const VISUALIZACIONES = {
  barras: 'Barras',
  lineas: 'Líneas',
  torta: 'Torta',
  kpi: 'KPI',
  tabla: 'Tabla',
}

function valorMetrica({ suma, cantidad }, metrica) {
  if (metrica === 'cantidad_siniestros') return cantidad
  if (metrica === 'monto_promedio') return cantidad ? Math.round(suma / cantidad) : 0
  return suma
}

export function totalMetrica(data, metrica) {
  const suma = data.reduce((acc, s) => acc + s.monto, 0)
  return valorMetrica({ suma, cantidad: data.length }, metrica)
}

// Agrupa los siniestros por una dimensión y calcula la métrica de cada grupo
export function agregarPor(data, dimension, metrica) {
  const campo = dimension === 'mes' ? 'fecha' : dimension
  const grupos = new Map()
  data.forEach((s) => {
    const grupo = grupos.get(s[campo]) ?? { categoria: s[campo], suma: 0, cantidad: 0 }
    grupo.suma += s.monto
    grupo.cantidad += 1
    grupos.set(s[campo], grupo)
  })
  const filas = [...grupos.values()].map((g) => ({ categoria: g.categoria, valor: valorMetrica(g, metrica) }))
  return dimension === 'mes'
    ? filas.sort((a, b) => a.categoria.localeCompare(b.categoria))
    : filas.sort((a, b) => b.valor - a.valor)
}

function normalizar(valor) {
  return String(valor ?? '').trim()
}

// Acepta montos como 850000, "850.000" o "$ 850.000" (formato chileno)
function parsearMonto(valor) {
  if (typeof valor === 'number') return valor
  const limpio = normalizar(valor).replace(/[$\s]/g, '')
  if (!limpio) return NaN
  return Number(/^\d{1,3}(\.\d{3})+$/.test(limpio) ? limpio.replaceAll('.', '') : limpio.replace(',', '.'))
}

function encontrarCatalogo(valor, opciones) {
  const norm = normalizar(valor).toLowerCase()
  return opciones.find((op) => op.toLowerCase() === norm)
}

// Valida cada fila importada contra el catálogo autorizado del dominio
// (RN-03: solo se aceptan valores existentes en el catálogo).
export function validarFilasImportadas(filas) {
  const validos = []
  const rechazados = []

  filas.forEach((fila, i) => {
    const claves = Object.keys(fila).reduce((acc, k) => {
      acc[k.trim().toLowerCase()] = fila[k]
      return acc
    }, {})

    const producto = encontrarCatalogo(claves.producto, productos)
    const region = encontrarCatalogo(claves.region ?? claves['región'], regiones)
    const estado = encontrarCatalogo(claves.estado, estados)
    const fecha = normalizar(claves.fecha)
    const monto = parsearMonto(claves.monto ?? claves.monto_pagado)

    const errores = []
    if (!producto) errores.push('producto no está en el catálogo')
    if (!region) errores.push('región no está en el catálogo')
    if (!estado) errores.push('estado no está en el catálogo')
    if (!/^\d{4}-\d{2}$/.test(fecha)) errores.push('fecha debe tener formato AAAA-MM')
    if (Number.isNaN(monto) || monto <= 0) errores.push('monto inválido')

    if (errores.length) {
      rechazados.push({ fila: i + 2, errores })
      return
    }

    validos.push({
      id: `IMP-${Date.now()}-${i}`,
      poliza: normalizar(claves.poliza ?? claves['póliza']) || `POL-IMP-${i}`,
      clienteId: normalizar(claves.cliente ?? claves.clienteid) || `CLI-IMP-${i}`,
      producto,
      region,
      estado,
      fecha,
      monto,
    })
  })

  return { validos, rechazados }
}

const DIMENSION_POR_VISUALIZACION = { lineas: 'mes', torta: 'estado', barras: 'producto', tabla: 'producto', kpi: 'ninguno' }

// Completa metrica/agruparPor/visualizacion con valores coherentes cuando la
// interpretación (local, del backend o de un chat guardado antes) no los trae.
export function completarReporte(interpretacion = {}) {
  const { metrica, agruparPor, visualizacion } = interpretacion
  const agrupa = DIMENSIONES[agruparPor] && agruparPor !== 'ninguno'
  const vis = VISUALIZACIONES[visualizacion]
    ? visualizacion
    : agrupa ? (agruparPor === 'mes' ? 'lineas' : 'barras') : 'kpi'
  return {
    metrica: METRICAS[metrica] ? metrica : 'cantidad_siniestros',
    agruparPor: agrupa || vis === 'kpi' ? (agrupa ? agruparPor : 'ninguno') : DIMENSION_POR_VISUALIZACION[vis],
    visualizacion: vis,
  }
}
