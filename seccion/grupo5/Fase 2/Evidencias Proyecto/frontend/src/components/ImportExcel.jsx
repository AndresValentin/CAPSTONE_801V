import { useRef, useState } from 'react'
import readXlsxFile from 'read-excel-file/browser'
import { FileUp, Download, CheckCircle2, AlertTriangle } from 'lucide-react'
import { validarFilasImportadas } from '../data/mockData.js'
import './ImportExcel.css'

function formatearCelda(valor) {
  if (valor instanceof Date) {
    const yyyy = valor.getFullYear()
    const mm = String(valor.getMonth() + 1).padStart(2, '0')
    return `${yyyy}-${mm}`
  }
  return valor
}

async function leerXlsx(file) {
  const filas = await readXlsxFile(file)
  const [encabezado, ...resto] = filas
  const headers = encabezado.map((h) => String(h).trim())
  return resto.map((fila) => {
    const obj = {}
    headers.forEach((h, i) => { obj[h] = formatearCelda(fila[i]) })
    return obj
  })
}

async function leerCsv(file) {
  const texto = await file.text()
  const [primeraLinea, ...lineas] = texto.trim().split(/\r?\n/)
  const headers = primeraLinea.split(',').map((h) => h.trim())
  return lineas.filter(Boolean).map((linea) => {
    const valores = linea.split(',')
    const obj = {}
    headers.forEach((h, i) => { obj[h] = valores[i]?.trim() })
    return obj
  })
}

export default function ImportExcel({ onImportar }) {
  const inputRef = useRef(null)
  const [estado, setEstado] = useState('idle') // idle | procesando | listo | error
  const [resumen, setResumen] = useState(null)

  async function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setEstado('procesando')
    setResumen(null)

    try {
      const esCsv = file.name.toLowerCase().endsWith('.csv')
      const filas = esCsv ? await leerCsv(file) : await leerXlsx(file)
      const { validos, rechazados } = validarFilasImportadas(filas)

      if (validos.length) onImportar?.(validos)

      setResumen({
        archivo: file.name,
        total: filas.length,
        importados: validos.length,
        rechazados: rechazados.length,
        detalleErrores: rechazados.slice(0, 3),
      })
      setEstado('listo')
    } catch {
      setEstado('error')
      setResumen(null)
    } finally {
      e.target.value = ''
    }
  }

  function descargarPlantilla() {
    const contenido = 'producto,region,estado,fecha,monto\nAutomotriz,Metropolitana,Aprobado,2026-03,850000\n'
    const blob = new Blob([contenido], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'plantilla_siniestros.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="import-module">
      <div className="module-title">
        <span className="module-title-icon"><FileUp size={13} /></span>
        Importar datos
      </div>
      <p className="module-hint">Carga un Excel/CSV con columnas: producto, region, estado, fecha, monto.</p>

      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        onChange={handleFile}
        className="import-input"
        id="import-file-input"
      />
      <label htmlFor="import-file-input" className="import-dropzone">
        {estado === 'procesando' ? 'Procesando…' : 'Seleccionar archivo o arrastrar aquí'}
      </label>

      {resumen && (
        <div className={`import-summary ${resumen.rechazados ? 'import-summary-warn' : 'import-summary-ok'}`}>
          <div className="import-summary-row">
            {resumen.rechazados ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
            <span>{resumen.importados} importados · {resumen.rechazados} rechazados</span>
          </div>
          {resumen.detalleErrores.length > 0 && (
            <ul className="import-errors">
              {resumen.detalleErrores.map((err, i) => (
                <li key={i}>Fila {err.fila}: {err.errores.join(', ')}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {estado === 'error' && (
        <div className="import-summary import-summary-warn">
          <div className="import-summary-row">
            <AlertTriangle size={13} /> No se pudo leer el archivo.
          </div>
        </div>
      )}

      <button type="button" className="template-link" onClick={descargarPlantilla}>
        <Download size={12} /> Descargar plantilla CSV
      </button>
    </div>
  )
}
