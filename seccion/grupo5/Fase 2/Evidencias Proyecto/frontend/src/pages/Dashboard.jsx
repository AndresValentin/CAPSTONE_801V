import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Database, LogOut, PanelLeft } from 'lucide-react'
import Sidebar from '../components/Sidebar.jsx'
import FiltersPanel from '../components/FiltersPanel.jsx'
import DashboardPanel from '../components/DashboardPanel.jsx'
import ChatCopilot from '../components/ChatCopilot.jsx'
import ReportTemplate from '../components/ReportTemplate.jsx'
import ReporteBD from '../components/ReporteBD.jsx'
import { FILTROS_INICIALES, completarFiltros, filtrarSiniestros, siniestrosBase } from '../data/mockData.js'
import { useConversaciones, reportesDe } from '../hooks/useConversaciones.js'
import { cerrarSesion, interpretar, leerSesion, usaBackend } from '../lib/api.js'
import { procesarArchivo } from '../lib/importacion.js'
import { guardarLocal, leerLocal } from '../lib/persistencia.js'
import './Dashboard.css'

const CLAVE_IMPORTADOS = 'bi-copilot:importados'

export default function Dashboard() {
  const navigate = useNavigate()
  const [sesion] = useState(leerSesion)
  const chats = useConversaciones()
  // Al entrar se muestra el último reporte del chat activo; un chat vacío muestra la plantilla
  const [reporteActivo, setReporteActivo] = useState(() => reportesDe(chats.activa).at(-1) ?? null)
  const [filtros, setFiltros] = useState(() => reporteActivo?.filtros ?? FILTROS_INICIALES)
  const [importados, setImportados] = useState(() => leerLocal(CLAVE_IMPORTADOS, []))
  const [pensandoEn, setPensandoEn] = useState(null)
  const [sidebarAbierto, setSidebarAbierto] = useState(() => window.innerWidth > 900)

  useEffect(() => { guardarLocal(CLAVE_IMPORTADOS, importados) }, [importados])

  // Con backend, sin sesión no se sabe qué dominios puede consultar el usuario
  useEffect(() => {
    if (usaBackend && !sesion) navigate('/', { replace: true })
  }, [sesion, navigate])

  function salir() {
    cerrarSesion()
    navigate('/')
  }

  const dataset = useMemo(() => [...siniestrosBase, ...importados], [importados])
  const datosFiltrados = useMemo(() => filtrarSiniestros(dataset, filtros), [dataset, filtros])

  function verReporte(mensaje, conversacionId) {
    if (conversacionId) chats.seleccionar(conversacionId)
    setFiltros(mensaje.filtros)
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
      setReporteActivo(null)
    }
  }

  function nuevoChat() {
    chats.nuevaConversacion()
    cerrarSidebarEnMovil()
    setFiltros(FILTROS_INICIALES)
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
      const resultado = await interpretar(pregunta)
      if (resultado.estado === 'validado') {
        const mensaje = chats.agregarMensaje(conversacionId, {
          rol: 'asistente',
          tipo: 'validado',
          pregunta,
          texto: 'Solicitud validada contra el catálogo. Generé el reporte en el dashboard.',
          interpretacion: resultado.interpretacion,
          // El backend trae los datos ya calculados; en modo demo se filtran en el navegador
          ...(resultado.resultado
            ? { resultado: resultado.resultado, filtros: FILTROS_INICIALES }
            : { filtros: completarFiltros(resultado.interpretacion.filtros) }),
        })
        verReporte(mensaje)
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
            {reporteActivo?.resultado ? (
              <ReporteBD reporte={reporteActivo} />
            ) : reporteActivo ? (
              <>
                <FiltersPanel filtros={filtros} setFiltros={setFiltros} resultados={datosFiltrados.length} />
                <DashboardPanel datos={datosFiltrados} filtros={filtros} reporte={reporteActivo} />
              </>
            ) : (
              <ReportTemplate />
            )}
          </div>

          <ChatCopilot
            conversacion={chats.activa}
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
