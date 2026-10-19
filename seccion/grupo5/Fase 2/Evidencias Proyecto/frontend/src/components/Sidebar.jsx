import { useMemo, useState } from 'react'
import { SquarePen, Search, Trash2, FileUp, BrainCircuit, ChevronDown, MessageSquare } from 'lucide-react'
import { reportesDe } from '../hooks/useConversaciones.js'
import { resumenPorMes } from '../data/mockData.js'
import { proyectarMonto } from '../lib/regression.js'
import { formatCLPCorto } from '../lib/formato.js'
import ImportExcel from './ImportExcel.jsx'
import MLPanel from './MLPanel.jsx'
import './Sidebar.css'

const DIA = 24 * 60 * 60 * 1000

function grupoFecha(iso) {
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const fecha = new Date(iso)
  if (fecha >= hoy) return 'Hoy'
  if (fecha >= hoy - DIA) return 'Ayer'
  if (fecha >= hoy - 7 * DIA) return 'Últimos 7 días'
  return 'Anteriores'
}

function agruparPorFecha(conversaciones) {
  const grupos = []
  conversaciones.forEach((c) => {
    const nombre = grupoFecha(c.actualizada)
    const grupo = grupos.at(-1)?.nombre === nombre ? grupos.at(-1) : grupos[grupos.push({ nombre, items: [] }) - 1]
    grupo.items.push(c)
  })
  return grupos
}

function Modulo({ icono: Icono, titulo, resumen, abierto, onToggle, children }) {
  return (
    <section className={`sb-module ${abierto ? 'sb-module-open' : ''}`}>
      <button type="button" className="sb-module-head" onClick={onToggle} aria-expanded={abierto}>
        <span className="sb-module-icon"><Icono size={14} /></span>
        <span className="sb-module-text">
          <span className="sb-module-title">{titulo}</span>
          {resumen && <span className="sb-module-summary">{resumen}</span>}
        </span>
        <ChevronDown size={15} className="sb-module-chevron" />
      </button>
      {abierto && <div className="sb-module-body">{children}</div>}
    </section>
  )
}

export default function Sidebar({
  abierto, conversaciones, activaId, onSeleccionarConversacion, onNuevoChat, onEliminarConversacion,
  onImportar, totalImportados, onLimpiarImportados, datos,
}) {
  const [busqueda, setBusqueda] = useState('')
  const [moduloAbierto, setModuloAbierto] = useState(null) // 'importar' | 'ml' | null

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    return q ? conversaciones.filter((c) => c.titulo.toLowerCase().includes(q)) : conversaciones
  }, [busqueda, conversaciones])

  const analisis = useMemo(() => proyectarMonto(resumenPorMes(datos)), [datos])

  function alternar(modulo) {
    setModuloAbierto((actual) => (actual === modulo ? null : modulo))
  }

  return (
    <aside className={`sidebar ${abierto ? '' : 'sidebar-closed'}`}>
      <button type="button" className="sb-new" onClick={onNuevoChat}>
        <SquarePen size={15} /> Nuevo reporte
      </button>

      <label className="sb-search">
        <Search size={14} />
        <input
          type="search"
          placeholder="Buscar chats"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </label>

      <nav className="sb-history" aria-label="Historial de chats">
        {filtradas.length === 0 && <p className="sb-empty">No hay chats que coincidan.</p>}

        {agruparPorFecha(filtradas).map((grupo) => (
          <div key={grupo.nombre} className="sb-group">
            <p className="sb-group-label">{grupo.nombre}</p>
            {grupo.items.map((c) => {
              const total = reportesDe(c).length
              return (
                <div key={c.id} className={`sb-item ${c.id === activaId ? 'sb-item-active' : ''}`}>
                  <button type="button" className="sb-item-main" onClick={() => onSeleccionarConversacion(c.id)} title={c.titulo}>
                    <MessageSquare size={14} className="sb-item-icon" />
                    <span className="sb-item-title">{c.titulo}</span>
                    {total > 0 && <span className="sb-item-count" title={`${total} reportes`}>{total}</span>}
                  </button>
                  <button
                    type="button"
                    className="sb-item-delete"
                    title="Eliminar chat"
                    onClick={() => onEliminarConversacion(c.id)}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="sb-modules">
        <Modulo
          icono={FileUp}
          titulo="Importar Excel"
          resumen={totalImportados ? `${totalImportados} registros importados` : 'Sube .xlsx o .csv'}
          abierto={moduloAbierto === 'importar'}
          onToggle={() => alternar('importar')}
        >
          <ImportExcel onImportar={onImportar} totalImportados={totalImportados} onLimpiar={onLimpiarImportados} />
        </Modulo>

        <Modulo
          icono={BrainCircuit}
          titulo="Regresión lineal"
          resumen={analisis ? `Proyección ${analisis.proximoMes}: ${formatCLPCorto(analisis.proyeccion)}` : 'Sin datos suficientes'}
          abierto={moduloAbierto === 'ml'}
          onToggle={() => alternar('ml')}
        >
          <MLPanel analisis={analisis} />
        </Modulo>
      </div>
    </aside>
  )
}
