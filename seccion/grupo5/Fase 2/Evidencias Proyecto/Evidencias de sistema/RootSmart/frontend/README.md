# RootSmart — Frontend (React + Vite)

Interfaz web de RootSmart: inicio de sesión, chat con el copiloto, dashboards con gráficos y mapa de Chile, filtros que se recalculan sin IA, proyecciones, carpetas y dashboards compartidos, y administración de usuarios y solicitudes de acceso.

## Tecnologías

React 19, Vite, React Router, Recharts (gráficos), Lucide (íconos) y read-excel-file (importación de Excel). Lint con Oxlint.

## Cómo correrlo

```bash
npm install
echo VITE_API_URL=http://localhost:8000 > .env.local   # URL del backend
npm run dev                                           # http://localhost:5173
```

Sin `VITE_API_URL` el frontend funciona en **modo demo**, con las reglas locales de `src/lib/copilot.js` y sin base de datos.

Con Docker, el `Dockerfile` compila la aplicación y la sirve con nginx en el puerto 80 (`docker compose up` la publica en http://localhost:8080).

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo en el puerto 5173 |
| `npm run build` | Compila a `dist/` |
| `npm run lint` | Revisa el código con Oxlint |

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/pages/` | Pantallas: `Login`, `Dashboard` (chat y reporte), `Proyecciones`, `Biblioteca` (carpetas) y `VistaDashboard` |
| `src/components/` | Chat, panel de filtros, gráficos, mapa, modales de usuarios, permisos y recuperación de clave |
| `src/lib/api.js` | Llamadas al backend con el token de sesión |
| `src/lib/` | Formato de cifras, gráficos, análisis, importación y persistencia local |
| `src/hooks/` | Historial de conversaciones y proyecciones |

El token de sesión se guarda en el navegador y viaja en el encabezado `Authorization`. El backend saca el usuario del token, nunca de lo que envíe el navegador.
