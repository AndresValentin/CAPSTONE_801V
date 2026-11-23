import { useRef, useState } from 'react'
import { calcularProyeccion, listarProyecciones } from '../lib/api.js'

export const claveSerie = (s) => `${s.dominio}:${s.metrica}`

// Cada cuánto se vuelve a calcular la serie en pantalla, sin que el usuario haga nada:
// si entró un mes nuevo a la base, la proyección avanza sola
const VIGENCIA_MS = 5 * 60 * 1000

// Estado de la pantalla "Proyecciones": las series que se pueden proyectar y la elegida.
// Guarda cada cálculo unos minutos para no repetir la consulta al volver a una serie.
export function useProyecciones(onSesionExpirada) {
  const [series, setSeries] = useState(null)
  const [elegida, setElegida] = useState('')
  const [calculo, setCalculo] = useState({ cargando: false, error: '', respuesta: null, calculadoEn: null })
  const resultados = useRef(new Map()) // clave -> { respuesta, en }
  const ultimaPedida = useRef('')

  function fallo(err, texto) {
    if (err.estado === 401) onSesionExpirada?.()
    else setCalculo({ cargando: false, error: err.estado === 0 ? 'Sin conexión con el backend.' : err.message || texto, respuesta: null, calculadoEn: null })
  }

  // `silencioso`: actualiza por detrás sin borrar lo que se ve (refresco automático)
  async function elegir(clave, lista = series, { silencioso = false } = {}) {
    const serie = lista?.find((s) => claveSerie(s) === clave)
    if (!serie) return
    setElegida(clave)
    ultimaPedida.current = clave
    const guardada = resultados.current.get(clave)
    if (guardada && !silencioso && Date.now() - guardada.en < VIGENCIA_MS) {
      setCalculo({ cargando: false, error: '', respuesta: guardada.respuesta, calculadoEn: guardada.en })
      return
    }
    if (!silencioso) setCalculo({ cargando: true, error: '', respuesta: null, calculadoEn: null })
    try {
      const r = await calcularProyeccion(serie.dominio, serie.metrica)
      if (ultimaPedida.current !== clave) return // el usuario ya eligió otra serie
      if (r.estado !== 'validado') {
        if (!silencioso) setCalculo({ cargando: false, error: r.motivo, respuesta: null, calculadoEn: null })
        return
      }
      const en = Date.now()
      resultados.current.set(clave, { respuesta: r, en })
      setCalculo({ cargando: false, error: '', respuesta: r, calculadoEn: en })
    } catch (err) {
      // Un refresco automático que falla deja a la vista el último cálculo bueno
      if (ultimaPedida.current === clave && !silencioso) fallo(err, 'No se pudo calcular la proyección.')
    }
  }

  // Se llama al abrir la pantalla: carga las series y calcula la primera recomendada
  async function iniciar() {
    if (series !== null || calculo.cargando) return
    setCalculo({ cargando: true, error: '', respuesta: null, calculadoEn: null })
    try {
      const { series: lista } = await listarProyecciones()
      setSeries(lista)
      if (lista.length === 0) {
        setCalculo({ cargando: false, error: '', respuesta: null, calculadoEn: null })
        return
      }
      await elegir(claveSerie(lista[0]), lista)
    } catch (err) {
      fallo(err, 'No se pudieron cargar las series.')
    }
  }

  // Refresco automático de la serie en pantalla (lo programa la pantalla cada VIGENCIA_MS)
  function actualizar() {
    if (elegida && !calculo.cargando) elegir(elegida, series, { silencioso: true })
  }

  const serie = series?.find((s) => claveSerie(s) === elegida) ?? null
  return { series, serie, elegida, ...calculo, iniciar, elegir, actualizar, VIGENCIA_MS }
}
