import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Database, LogOut, PanelLeft } from 'lucide-react'
import Sidebar from '../components/Sidebar.jsx'
import FiltersPanel from '../components/FiltersPanel.jsx'
import DashboardPanel from '../components/DashboardPanel.jsx'
import ChatCopilot from '../components/ChatCopilot.jsx'
import ReportTemplate from '../components/ReportTemplate.jsx'
import ReporteBD from '../components/ReporteBD.jsx'
import FiltrosBD from '../components/FiltrosBD.jsx'
import { FILTROS_INICIALES, completarFiltros, filtrarSiniestros, siniestrosBase } from '../data/mockData.js'
import { useConversaciones, reportesDe } from '../hooks/useConversaciones.js'
import {
  cerrarSesion, interpretar, leerSesion, obtenerCatalogo, reejecutarReporte, usaBackend,
} from '../lib/api.js'
import { procesarArchivo } from '../lib/importacion.js'
import { guardarLocal, leerLocal } from '../lib/persistencia.js'
import './Dashboard.css'

const CLAVE_IMPORTADOS = 'bi-copilot:importados'
const PANEL_VACIO = { dominio: '', filtros: {}, desde: '', hasta: '' }

// Filtros del panel a partir del plan de un reporte del backend
function panelDesdePlan(plan) {
  return {
    dominio: plan.dominio,
    filtros: Object.fromEntries(plan.filtros.map((f) => [f.campo, f.valor])),
    desde: plan.desde,
    hasta: plan.hasta,
  }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [sesion] = useState(leerSesion)
  const chats = useConversaciones(sesion?.usuario)
  // Chat que el usuario tiene abierto ahora (las respuestas pueden llegar después de cambiarlo)
  const activaIdRef = useRef(chats.activa.id)
  useEffect(() => { activaIdRef.current = chats.activa.id }, [chats.activa.id])
  // Al entrar se muestra el último reporte del chat activo; un chat vacío muestra la plantilla
  const [reporteActivo, setReporteActivo] = useState(() => reportesDe(chats.activa).at(-1) ?? null)
  const [filtros, setFiltros] = useState(() => reporteActivo?.filtros ?? FILTROS_INICIALES)
  const [importados, setImportados] = useState(() => leerLocal(CLAVE_IMPORTADOS, []))
  const [pensandoEn, setPensandoEn] = useState(null)
  const [sidebarAbierto, setSidebarAbierto] = useState(() => window.innerWidth > 900)
  // Modo backend: filtros disponibles (según permisos) y los elegidos en el panel
  const [catalogoBD, setCatalogoBD] = useState(null)
  const [panel, setPanel] = useState(() => (reporteActivo?.plan ? panelDesdePlan(reporteActivo.plan) : PANEL_VACIO))
  const [estadoPanel, setEstadoPanel] = useState({ actualizando: false, error: '' })
  // Cada recálculo lleva un número; solo se aplica la respuesta del último.
  // Así una respuesta lenta no pisa a una más nueva ni cae sobre otro reporte.
  const ultimoRecalculo = useRef(0)

  useEffect(() => { guardarLocal(CLAVE_IMPORTADOS, importados) }, [importados])

  // Con backend, sin sesión no se sabe qué dominios puede consultar el usuario
  useEffect(() => {
    if (usaBackend && !sesion) navigate('/', { replace: true })
  }, [sesion, navigate])

  useEffect(() => {
    if (!usaBackend || !sesion) return
    obtenerCatalogo()
      .then(setCatalogoBD)
      .catch(() => {}) // sin catálogo el panel no se muestra; el detalle quedó en la consola
  }, [sesion])

  function salir() {
    cerrarSesion()
    navigate('/')
  }

  // Cambiar un filtro del panel recalcula el reporte en pantalla (sin pasar por la IA)
  // si es del mismo dominio; si no, el filtro queda listo para la próxima pregunta.
  function descartarRecalculos() {
    ultimoRecalculo.current += 1
    setEstadoPanel({ actualizando: false, error: '' })
  }

  async function cambiarPanel(nuevo) {
    setPanel(nuevo)
    const reporte = reporteActivo
    const plan = reporte?.plan
    if (!plan || plan.dominio !== nuevo.dominio) {
      descartarRecalculos()
      return
    }
    if (nuevo.desde && nuevo.hasta && nuevo.desde > nuevo.hasta) {
      ultimoRecalculo.current += 1
      setEstadoPanel({ actualizando: false, error: 'El inicio del rango es posterior al término.' })
      return
    }

    const numero = ++ultimoRecalculo.current
    const conversacionId = chats.activa.id
    setEstadoPanel({ actualizando: true, error: '' })
    const planNuevo = {
      ...plan,
      filtros: Object.entries(nuevo.filtros).map(([campo, valor]) => ({ campo, valor })),
      desde: nuevo.desde,
      hasta: nuevo.hasta,
    }
    try {
      const r = await reejecutarReporte(reporte.pregunta, planNuevo)
      if (numero !== ultimoRecalculo.current) return
      if (r.estado !== 'validado') {
        setEstadoPanel({ actualizando: false, error: `No se aplicaron los filtros: ${r.motivo}` })
        return
      }
      const cambios = { plan: r.plan, interpretacion: r.interpretacion, resultado: r.resultado }
      chats.actualizarMensaje(conversacionId, reporte.id, cambios)
      setReporteActivo((prev) => (prev?.id === reporte.id ? { ...prev, ...cambios } : prev))
      setEstadoPanel({ actualizando: false, error: '' })
    } catch (err) {
      if (numero !== ultimoRecalculo.current) return
      if (err.estado === 401) {
        salir()
        return
      }
      setEstadoPanel({ actualizando: false, error: 'No se pudieron aplicar los filtros. Intenta nuevamente.' })
    }
  }

  const dataset = useMemo(() => [...siniestrosBase, ...importados], [importados])
  const datosFiltrados = useMemo(() => filtrarSiniestros(dataset, filtros), [dataset, filtros])

  function verReporte(mensaje, conversacionId) {
    if (conversacionId) chats.seleccionar(conversacionId)
    setFiltros(mensaje.filtros)
    descartarRecalculos()
    setPanel(mensaje.plan ? panelDesdePlan(mensaje.plan) : PANEL_VACIO)
    setReporteActivo(mensaje)
  }

  function cerrarSidebarEnMovil() {
    if (window.innerWidth <= 900) setSidebarAbierto(false)
  }

  function seleccionarConversacion(id) {
    chats.seleccionar(id)
    cerrarSidebarEnMovil()
    const conversacion = chats.conversaciones.find((c) => c.id === id)
    const ultimo = conversacion && reportesDe(conversacion).at(-1)
    if (ultimo) {
      verReporte(ultimo)
    } else {
      setFiltros(FILTROS_INICIALES)
      descartarRecalculos()
      setPanel(PANEL_VACIO)
      setReporteActivo(null)
    }
  }

  function nuevoChat() {
    chats.nuevaConversacion()
    cerrarSidebarEnMovil()
    setFiltros(FILTROS_INICIALES)
    descartarRecalculos()
    setPanel(PANEL_VACIO)
    setReporteActivo(null)
  }

  function eliminarChat(id) {
    if (id === chats.activa.id) {
      setReporteActivo(null)
      setFiltros(FILTROS_INICIALES)
    }
    chats.eliminarConversacion(id)
  }

  async function enviarPregunta(pregunta) {
    const conversacionId = chats.activa.id
    chats.agregarMensaje(conversacionId, { rol: 'usuario', texto: pregunta })
    setPensandoEn(conversacionId)

    try {
      const { dominio: _dominio, ...filtrosPanel } = panel
      const resultado = await interpretar(pregunta, filtrosPanel)
      if (resultado.estado === 'validado') {
        const mensaje = chats.agregarMensaje(conversacionId, {
          rol: 'asistente',
          tipo: 'validado',
          pregunta,
          texto: 'Solicitud validada contra el catálogo. Generé el reporte en el dashboard.',
          interpretacion: resultado.interpretacion,
          // El backend trae los datos ya calculados; en modo demo se filtran en el navegador
          ...(resultado.resultado
            ? { resultado: resultado.resultado, plan: resultado.plan, filtros: FILTROS_INICIALES }
            : { filtros: completarFiltros(resultado.interpretacion.filtros) }),
        })
        if (activaIdRef.current === conversacionId) verReporte(mensaje)
      } else {
        // 'aclaracion': faltan datos para armar el reporte y el asistente los pide.
        // 'rechazado': la solicitud no pasó la validación. En ambos casos el
        // dashboard sigue mostrando el último reporte válido.
        chats.agregarMensaje(conversacionId, {
          rol: 'asistente',
          tipo: resultado.estado === 'aclaracion' ? 'aclaracion' : 'rechazo',
          pregunta,
          texto: resultado.motivo,
        })
      }
    } catch (err) {
      // El detalle técnico ya quedó en la consola (lib/api.js)
      if (err.estado === 401) {
        salir()
        return
      }
      chats.agregarMensaje(conversacionId, {
        rol: 'asistente',
        tipo: 'error',
        texto: 'No pude generar el reporte en este momento. Intenta nuevamente en unos minutos.',
      })
    } finally {
      setPensandoEn(null)
    }
  }

  // Lo usan tanto el clip del chat como el módulo de importación del sidebar:
  // en ambos casos la carga queda registrada en el chat activo.
  async function importarArchivo(file) {
    const conversacionId = chats.activa.id
    chats.agregarMensaje(conversacionId, { rol: 'usuario', tipo: 'archivo', texto: file.name })
    setPensandoEn(conversacionId)

    try {
      const { archivo, total, validos, rechazados } = await procesarArchivo(file)
      if (validos.length) setImportados((prev) => [...prev, ...validos])

      const resumen = {
        archivo,
        total,
        importados: validos.length,
        rechazados: rechazados.length,
        detalleErrores: rechazados.slice(0, 3),
      }
      chats.agregarMensaje(conversacionId, {
        rol: 'asistente',
        tipo: 'importacion',
        texto: validos.length
          ? `Importé ${validos.length} de ${total} filas de ${archivo}. Ya puedes consultarlas en el chat.`
          : `Ninguna fila de ${archivo} pasó la validación del catálogo.`,
        resumen,
      })
      return resumen
    } catch (err) {
      chats.agregarMensaje(conversacionId, {
        rol: 'asistente',
        tipo: 'error',
        texto: `No se pudo leer ${file.name}. ${err.message}`,
      })
      throw err
    } finally {
      setPensandoEn(null)
    }
  }

  return (
    <div className="dashboard-screen">
      <header className="dashboard-header">
        <div className="brand">
          <button
            type="button"
            className="btn-sidebar-toggle"
            title={sidebarAbierto ? 'Ocultar historial' : 'Mostrar historial'}
            onClick={() => setSidebarAbierto((v) => !v)}
          >
            <PanelLeft size={17} />
          </button>
          <span className="brand-mark"><Sparkles size={15} strokeWidth={2.4} /></span>
          <span className="brand-name">BI Copilot</span>
        </div>
        <div className="header-meta">
          <span className="domain-pill">
            <Database size={13} />
            {sesion
              ? `${sesion.nombre} · ${sesion.dominios.map((d) => d.nombre).join(', ')}`
              : `Siniestros · ${dataset.length} registros`}
          </span>
          <button className="btn-logout" onClick={salir}>
            <LogOut size={14} /> Cerrar sesión
          </button>
        </div>
      </header>

      <div className="dashboard-body">
        <Sidebar
          abierto={sidebarAbierto}
          conversaciones={chats.conversaciones}
          activaId={chats.activa.id}
          onSeleccionarConversacion={seleccionarConversacion}
          onNuevoChat={nuevoChat}
          onEliminarConversacion={eliminarChat}
          onImportar={importarArchivo}
          totalImportados={importados.length}
          onLimpiarImportados={() => setImportados([])}
          datos={datosFiltrados}
        />
        {sidebarAbierto && <div className="sidebar-backdrop" onClick={() => setSidebarAbierto(false)} />}

        <main className="workspace">
          <div className="main-column">
            {usaBackend && (
              <FiltrosBD
                catalogo={catalogoBD}
                panel={panel}
                onCambiar={cambiarPanel}
                resultados={reporteActivo?.resultado?.cantidad}
                actualizando={estadoPanel.actualizando}
                error={estadoPanel.error}
              />
            )}
            {reporteActivo?.resultado ? (
              <ReporteBD reporte={reporteActivo} actualizando={estadoPanel.actualizando} />
            ) : reporteActivo ? (
              <>
                {!usaBackend && (
                  <FiltersPanel filtros={filtros} setFiltros={setFiltros} resultados={datosFiltrados.length} />
                )}
                <DashboardPanel datos={datosFiltrados} filtros={filtros} reporte={reporteActivo} />
              </>
            ) : (
              <ReportTemplate />
            )}
          </div>

          <ChatCopilot
            conversacion={chats.activa}
            catalogo={catalogoBD}
            pensando={pensandoEn === chats.activa.id}
            reporteActivoId={reporteActivo?.id}
            onEnviar={enviarPregunta}
            onAdjuntar={importarArchivo}
            onVerReporte={verReporte}
            onNuevoChat={nuevoChat}
          />
        </main>
      </div>
    </div>
  )
}
