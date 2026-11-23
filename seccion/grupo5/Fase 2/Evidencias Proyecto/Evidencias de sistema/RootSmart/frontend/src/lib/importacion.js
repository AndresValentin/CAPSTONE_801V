import readXlsxFile from 'read-excel-file/browser'
import { validarFilasImportadas } from '../data/mockData.js'

export const EXTENSIONES_ACEPTADAS = '.xlsx,.csv'

function formatearCelda(valor) {
  // read-excel-file entrega las fechas en UTC: con getters locales el 1 de marzo
  // quedaría como 28 de febrero en la zona horaria de Chile.
  if (valor instanceof Date) {
    const yyyy = valor.getUTCFullYear()
    const mm = String(valor.getUTCMonth() + 1).padStart(2, '0')
    return `${yyyy}-${mm}`
  }
  return valor
}

function filasAObjetos(encabezado, filas) {
  const headers = encabezado.map((h) => String(h ?? '').trim())
  return filas.map((fila) => {
    const obj = {}
    headers.forEach((h, i) => { obj[h] = formatearCelda(fila[i]) })
    return obj
  })
}

async function leerXlsx(file) {
  const [encabezado, ...resto] = await readXlsxFile(file)
  if (!encabezado) throw new Error('El archivo está vacío.')
  return filasAObjetos(encabezado, resto)
}

async function leerCsv(file) {
  const texto = await file.text()
  const lineas = texto.trim().split(/\r?\n/).filter((l) => l.trim())
  if (!lineas.length) throw new Error('El archivo está vacío.')
  // Excel en español exporta los CSV separados por ";"
  const separador = lineas[0].includes(';') ? ';' : ','
  const [encabezado, ...resto] = lineas.map((l) => l.split(separador).map((v) => v.trim()))
  return filasAObjetos(encabezado, resto)
}

// Lee un .xlsx/.csv y valida cada fila contra el catálogo autorizado.
export async function procesarArchivo(file) {
  const nombre = file.name.toLowerCase()
  const esCsv = nombre.endsWith('.csv')
  if (!esCsv && !nombre.endsWith('.xlsx')) {
    throw new Error('Formato no soportado. Usa un archivo .xlsx o .csv.')
  }

  const filas = esCsv ? await leerCsv(file) : await leerXlsx(file)
  const { validos, rechazados } = validarFilasImportadas(filas)
  return { archivo: file.name, total: filas.length, validos, rechazados }
}
