import { useRef, useState } from 'react'
import { calcularProyeccion, listarProyecciones } from '../lib/api.js'
import { formatMetrica } from '../lib/formato.js'

export const claveSerie = (s) => `${s.dominio}:${s.metrica}`

// Texto corto para la cabecera del módulo cerrado. `p` = useProyecciones()
export function resumenProyeccion(p) {
  const proyeccion = p.respuesta?.resultado?.proyeccion
  if (!p.serie || !proyeccion || proyeccion.omitida) return 'Regresión lineal con datos reales'
  const [siguiente] = proyeccion.meses
  return `${p.serie.etiqueta}: ${formatMetrica(siguiente.valor, p.serie.moneda)} en ${siguiente.mes}`
}

// Estado del módulo "Proyecciones" del menú lateral. Vive en el Sidebar (no en el panel)
// para no repetir las consultas cada vez que se cierra y abre el módulo.
// Nada se pide a la BD hasta que el usuario abre el módulo por primera vez.
export function useProyecciones(onSesionExpirada) {
  const [series, setSeries] = useState(null)
  const [elegida, setElegida] = useState('')
  const [calculo, setCalculo] = useState({ cargando: false, error: '', respuesta: null })
  const resultados = useRef(new Map()) // clave -> respuesta ya calculada
  const ultimaPedida = useRef('')

  function fallo(err, texto) {
    if (err.estado === 401) onSesionExpirada?.()
    else setCalculo({ cargando: false, error: err.estado === 0 ? 'Sin conexión con el backend.' : err.message || texto, respuesta: null })
  }

  async function elegir(clave, lista = series) {
    const serie = lista?.find((s) => claveSerie(s) === clave)
    if (!serie) return
    setElegida(clave)
    ultimaPedida.current = clave
    const guardada = resultados.current.get(clave)
    if (guardada) {
      setCalculo({ cargando: false, error: '', respuesta: guardada })
      return
    }
    setCalculo({ cargando: true, error: '', respuesta: null })
    try {
      const r = await calcularProyeccion(serie.dominio, serie.metrica)
      if (ultimaPedida.current !== clave) return // el usuario ya eligió otra serie
      if (r.estado !== 'validado') {
        setCalculo({ cargando: false, error: r.motivo, respuesta: null })
        return
      }
      resultados.current.set(clave, r)
      setCalculo({ cargando: false, error: '', respuesta: r })
    } catch (err) {
      if (ultimaPedida.current === clave) fallo(err, 'No se pudo calcular la proyección.')
    }
  }

  // Se llama al abrir el módulo: la primera vez carga las series y calcula la recomendada
  async function iniciar() {
    if (series !== null || calculo.cargando) return
    setCalculo({ cargando: true, error: '', respuesta: null })
    try {
      const { series: lista } = await listarProyecciones()
      setSeries(lista)
      if (lista.length === 0) {
        setCalculo({ cargando: false, error: '', respuesta: null })
        return
      }
      await elegir(claveSerie(lista[0]), lista)
    } catch (err) {
      fallo(err, 'No se pudieron cargar las series.')
    }
  }

  // Vuelve a consultar la BD (por ejemplo, después de una carga nueva de datos)
  function recalcular() {
    resultados.current.delete(elegida)
    elegir(elegida)
  }

  const serie = series?.find((s) => claveSerie(s) === elegida) ?? null
  return { series, serie, elegida, ...calculo, iniciar, elegir, recalcular }
}
