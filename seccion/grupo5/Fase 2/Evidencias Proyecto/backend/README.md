# BI Copilot — Backend (Python + FastAPI + Claude)

## El flujo, paso a paso

Base de datos: **SQL Server, `DB_BI_RUTA_SMART`** (scripts `00`–`14` de `Fase 3/database` + `15`–`17` de `db/sqlserver`).

```
Frontend (chat)                 Backend (este proyecto)                              SQL Server
───────────────                 ───────────────────────                              ──────────
usuario: USR_SIN      POST      1. dominios_autorizados()  qué puede ver el usuario ──►  seguridad.SEG_USUARIO_DOMINIO
"monto pagado por  ──────────►  2. rechazo_previo()        reglas fijas (RN-02), sin gastar IA
 región en barras" /api/consultas 3. catalogo.obtener()    tablas, columnas, relaciones ─►  meta.MET_TABLA / COLUMNA / RELACION
                                4. interpretar_con_ia()    Claude devuelve un PLAN JSON
                                   (solo ve el detalle de los dominios del usuario)
                                5. validar_plan()          ¿el usuario tiene ese dominio?
                                   ¿los valores existen en el catálogo? (no se confía en la IA)
                                6. construir_sql()         SQL con piezas del catálogo + parámetros (?)
                                7. db.ejecutar()           como bi_lector (solo SELECT) ─►  ods.ODS_SIN / FIN / SEG_*
                                8. registrar_consulta()    traza + tokens ──────────────►  seguridad.SEG_LOG_CONSULTA
        ◄─────────────────────  { estado, interpretacion, resultado }
```

**La idea central: la IA no escribe SQL.** Solo traduce lenguaje natural a un plan como este:

```json
{
  "accion": "consultar",
  "dominio": "SIN",
  "titulo": "Reserva de siniestros abiertos por tipo",
  "metrica": "monto_reserva",
  "agrupar_por": "tipo_siniestro",
  "filtros": [{ "campo": "estado_siniestro", "valor": "ABIERTO" }],
  "desde": "",
  "hasta": "",
  "tipo_salida": "grafico_barras"
}
```

Python convierte ese plan en SQL. Así:
- la IA no puede inventar tablas ni columnas (el schema de salida solo admite valores del catálogo),
- no hay inyección SQL (los valores van como parámetros y además se validan),
- cada usuario solo consulta sus dominios: si USR_SIN pide primas (FIN) recibe "Acceso no autorizado al dominio FIN",
- no hay escrituras: el SQL corre como `bi_lector`, que solo tiene SELECT sobre `ods` y `dim` (SQL Server rechaza DELETE/UPDATE y la lectura de `seguridad`/`meta`),
- todo queda auditado en `seguridad.SEG_LOG_CONSULTA` (usuario, pregunta, plan de la IA, SQL ejecutado y tokens).

## Archivos

| Archivo | Qué hace |
|---|---|
| `app/main.py` | Endpoints `GET /api/salud`, `POST /api/sesion` (login) y `POST /api/consultas` |
| `app/catalogo.py` | Capa semántica por dominio (SIN, FIN, SEG: métricas, agrupaciones y JOIN) que se habilita según `meta.*`. Los valores de los filtros salen de la BD |
| `app/ia.py` | Llamada a Claude con structured outputs → `PlanConsulta` |
| `app/consultas.py` | Reglas previas, validación del plan y del dominio, armado del SQL (serie del gráfico, total y detalle) |
| `app/db.py` | Conexión a SQL Server (pyodbc): seguridad, metadatos, ejecución como `bi_lector` y traza |
| `app/claves.py` / `app/sesion.py` | Hash de contraseñas (PBKDF2-SHA256 con sal) y token de sesión firmado |
| `db/sqlserver/15–17_*.sql` | **Propuesta para la BD** (siguen la numeración de `Fase 3/database`): tabla de traza `seguridad.SEG_LOG_CONSULTA`, usuario de solo lectura `bi_lector` y contraseñas (hash) de los usuarios |

## Cómo correrlo

1. Base de datos, en este orden (con SQL Server Management Studio o `sqlcmd`):
   - los scripts `00` a `13` de `Fase 3/database` (el `14` valida la instalación),
   - los scripts `15` a `17` de `backend/db/sqlserver`.

   Con sqlcmd (el `-f 65001` es para que las tildes y la ñ se carguen bien), desde Git Bash:

   ```bash
   cd "Fase 3/database"
   for f in 0*.sql 1[0-3]_*.sql; do sqlcmd -S "localhost\MSSQLSERVER01" -E -C -b -f 65001 -i "$f"; done
   cd "../../Fase 2/Evidencias Proyecto/backend/db/sqlserver"
   for f in 1[5-7]_*.sql; do sqlcmd -S "localhost\MSSQLSERVER01" -E -C -b -f 65001 -i "$f"; done
   ```

2. Backend:

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
   pip install -r requirements.txt
   copy .env.example .env            # pegar la API key de Anthropic y revisar DB_SERVER
   uvicorn app.main:app --reload --port 8000
   ```

   Requiere el "ODBC Driver 18 for SQL Server" instalado. Documentación interactiva: http://localhost:8000/docs

3. Frontend: crear `frontend/.env.local` con:

   ```
   VITE_API_URL=http://localhost:8000
   ```

   Con backend, se inicia sesión con un usuario de `seguridad.SEG_USUARIO` y su contraseña (en la demo, `1234` para todos):

   | Usuario | Puede consultar |
   |---|---|
   | `USR_SIN` | Siniestros |
   | `USR_FIN` | Finanzas |
   | `USR_SEG` | Seguros |
   | `USR_ADMIN` | Los tres |

   En la BD solo se guarda el hash de la clave (`DESC_CLAVE_HASH`), nunca la clave. Para cambiar una: `python -m app.claves "nueva clave"` y actualizar esa columna con el resultado.
   El login entrega un token firmado (8 horas). El backend saca el usuario de ese token, no de lo que mande el navegador, así que nadie puede hacerse pasar por `USR_ADMIN`.
   Sin `VITE_API_URL`, el frontend sigue funcionando en modo demo con las reglas locales de `src/lib/copilot.js`.

## Modelo de IA y costo

Se usa **Claude Haiku 5.5** (`claude-haiku-5-5`), el modelo más barato de Claude: US$0,10 por millón de tokens de entrada y US$0,50 por millón de salida (con prompts de hasta 100K tokens). Se cambia con `CLAUDE_MODEL` en `.env`.

Costo estimado por reporte (los datos de la BD **no** pasan por la IA, solo la pregunta y el catálogo):

| | Tokens aprox. | Costo con Haiku 5.5 |
|---|---|---|
| Entrada: instrucciones + catálogo + schema + pregunta | 1.000 – 1.500 | ~US$0,00015 |
| Salida: plan JSON (~120) + razonamiento breve | 150 – 450 | ~US$0,0002 |
| **Total por reporte** | **~1.200 – 2.000** | **~US$0,0004** (≈ 2.500 reportes por US$1) |

Los tokens reales de cada consulta quedan en `seguridad.SEG_LOG_CONSULTA` (`NUM_TOKENS_ENTRADA` / `NUM_TOKENS_SALIDA`).

## Coordinación con la base de datos

- Lo que el backend toma del modelo de `Fase 3/database`: usuarios, dominios y permisos (`seguridad.*`) y el catálogo (`meta.MET_TABLA`, `MET_COLUMNA`, `MET_RELACION`). Apagar `FLG_DISPONIBLE_IA` o `FLG_ACTIVO` de una tabla, columna o relación saca de los reportes lo que dependa de ella (el catálogo se recarga cada 5 minutos).
- Los reportes de SIN y FIN se unen con `ODS_SEG_SEGURO` (por `ID_ITEM`) para poder agrupar por producto y región, y los de SEG con `ODS_SEG_CLIENTE`, siguiendo `meta.MET_RELACION`. Esa unión solo aporta atributos descriptivos, no métricas de otro dominio.
- Los scripts `15` y `16` son una **propuesta** para revisar con quien diseña la BD. Si cambian nombres de tabla o columnas, se ajustan las definiciones de `app/catalogo.py`.

## Próximos pasos

1. Cambiar la clave de demostración `1234` y definir `SESSION_SECRET` antes de mostrar el sistema fuera del equipo.
2. Endpoints `GET/POST /api/conversaciones` para guardar el historial de chats en la BD en vez de localStorage.
3. `POST /api/importaciones` para que el Excel se guarde en la BD (hoy queda en el navegador).
4. Que la regresión lineal y el Excel importado usen los datos de la BD (hoy usan los datos de prueba del navegador).
