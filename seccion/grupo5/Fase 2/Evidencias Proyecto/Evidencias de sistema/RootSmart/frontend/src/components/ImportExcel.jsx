import { useState } from 'react'
import { Download, CheckCircle2, AlertTriangle, Trash2 } from 'lucide-react'
import { EXTENSIONES_ACEPTADAS } from '../lib/importacion.js'
import './ImportExcel.css'

export default function ImportExcel({ onImportar, totalImportados, onLimpiar }) {
  const [estado, setEstado] = useState('idle') // idle | procesando | listo | error
  const [resumen, setResumen] = useState(null)
  const [arrastrando, setArrastrando] = useState(false)

  async function importar(file) {
    if (!file || estado === 'procesando') return
    setEstado('procesando')
    setResumen(null)
    try {
      setResumen(await onImportar(file))
      setEstado('listo')
    } catch {
      setEstado('error')
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setArrastrando(false)
    importar(e.dataTransfer.files[0])
  }

  function descargarPlantilla() {
    const contenido = 'producto,region,estado,fecha,monto\nAutomotriz,Metropolitana,Aprobado,2026-03,850000\n'
    const blob = new Blob([contenido], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'plantilla_siniestros.csv'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  return (
    <div className="import-module">
      <p className="module-hint">
        Columnas: producto, region, estado, fecha, monto. La carga queda registrada en el chat activo.
      </p>

      <input
        type="file"
        accept={EXTENSIONES_ACEPTADAS}
        onChange={(e) => { importar(e.target.files[0]); e.target.value = '' }}
        className="import-input"
        id="import-file-input"
      />
      <label
        htmlFor="import-file-input"
        className={`import-dropzone ${arrastrando ? 'import-dropzone-active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setArrastrando(true) }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={handleDrop}
      >
        {estado === 'procesando' ? 'Procesando…' : 'Selecciona o arrastra un .xlsx / .csv'}
      </label>

      {estado === 'listo' && resumen && (
        <div className={`import-summary ${resumen.rechazados ? 'import-summary-warn' : 'import-summary-ok'}`}>
          <div className="import-summary-row">
            {resumen.rechazados ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
            <span>{resumen.importados} importados · {resumen.rechazados} rechazados</span>
          </div>
          {resumen.detalleErrores.length > 0 && (
            <ul className="import-errors">
              {resumen.detalleErrores.map((err) => (
                <li key={err.fila}>Fila {err.fila}: {err.errores.join(', ')}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {estado === 'error' && (
        <div className="import-summary import-summary-warn">
          <div className="import-summary-row">
            <AlertTriangle size={13} /> No se pudo leer el archivo. Revisa el detalle en el chat.
          </div>
        </div>
      )}

      <div className="import-footer">
        <button type="button" className="template-link" onClick={descargarPlantilla}>
          <Download size={12} /> Plantilla CSV
        </button>
        {totalImportados > 0 && (
          <button type="button" className="template-link template-link-danger" onClick={onLimpiar}>
            <Trash2 size={12} /> Quitar {totalImportados}
          </button>
        )}
      </div>
    </div>
  )
}
