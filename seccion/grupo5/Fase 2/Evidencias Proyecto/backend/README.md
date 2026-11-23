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
| `app/analisis.py` | Comparación con el período anterior o el año anterior (solo métricas que lo permiten) y proyección por suavizamiento exponencial con tendencia (Holt), con cambios de nivel y meses atípicos |
| `db/sqlserver/15–17_*.sql` | **Propuesta para la BD** (siguen la numeración de `Fase 3/database`): tabla de traza `seguridad.SEG_LOG_CONSULTA`, usuario de solo lectura `bi_lector` y contraseñas (hash) de los usuarios |
| `db/sqlserver/25_CREATE_DASHBOARDS.sql` | Schema `app`: carpetas compartidas, miembros (LECTOR / EDITOR) y dashboards guardados (RF-022) |
| `db/sqlserver/26_DASHBOARD_PERMISO.sql` | Permiso por dashboard: un miembro puede tener en un dashboard un rol distinto al de la carpeta |

## Comparación de períodos y proyección

Cada métrica del catálogo dice si se puede comparar (`Medida.comparable` en `catalogo.py`):

| Valor | Significado | Ejemplos |
|---|---|---|
| `si` | Mide lo ocurrido en el período: se compara y se proyecta | Cantidad de siniestros, primas netas, pólizas emitidas |
| `advertencia` | Se compara, con una nota, pero no se proyecta | Monto pagado y recuperado (los siniestros recientes aún reciben pagos), cuotas pagadas |
| `no` | Refleja el estado de hoy: no se compara ni se proyecta, y se explica por qué | Monto en reserva, cuotas pendientes y vencidas |

Filtrar o agrupar por un estado (del siniestro, de la cuota o de la póliza) agrega una advertencia, porque es el estado de hoy. La proyección (3 meses) usa solo meses completos, necesita al menos 6 y no se calcula para cuotas, porque las futuras ya están programadas. Estas reglas son de negocio: el responsable de datos debe validarlas.

**Cómo se proyecta.** Suavizamiento exponencial con tendencia amortiguada (Holt), el mismo tipo de método del pronóstico de Power BI. Recorre la serie mes a mes con un nivel y una tendencia, y los corrige con cada mes real. Sus tres parámetros (cuánto pesa el último mes, qué tan rápido cambia la tendencia y cuánto se frena hacia adelante) se eligen con los datos: la combinación cuyos pronósticos a un mes habrían errado menos en la historia. Se usaba una regresión lineal sobre toda la historia, pero si la serie venía bajando la recta seguía el promedio de los años anteriores y la proyección "saltaba" hacia arriba (por ejemplo, 2, 2, 2, 1 movimientos de prima proyectaban 213). Ahora:

- la proyección parte del último nivel y sigue la dirección de la tendencia reciente: si baja, sigue bajando y se va frenando (nunca bajo 0 si la métrica no tiene negativos);
- si hubo un salto brusco que se mantuvo (un cambio de nivel, como de ~650 M a ~2 M), se entrena solo con los meses desde el salto; con menos de 4 meses no se proyecta;
- con menos de 8 meses no se estima tendencia: se proyecta el nivel actual;
- el rango cubre ±2 errores típicos y se abre con la distancia; los meses atípicos aislados se informan, pero no se quitan;
- avisa si los últimos meses cayeron a menos de la mitad (posible carga incompleta), si la tendencia llega a cero, si la serie varía mucho o si los datos terminan antes del último mes completo.

No modela estacionalidad (por ejemplo, un peak cada diciembre): con varios años de datos se podría pasar a Holt-Winters.

### Dashboards completos ("dashboard de siniestros de abril")

La IA entiende el contexto del negocio (qué es una prima, un siniestro, una reserva o la morosidad, y cómo se dice: "gasto", "ingresos", "ventas", "deuda") y fechas como "abril" o "el último trimestre". Si se pide un dashboard, tablero o "cómo nos fue" de un área, el plan trae `"accion": "dashboard"` y el backend arma un conjunto curado de gráficos (`catalogo.PAQUETES`): cifras clave contra el período anterior, la tendencia de los últimos 12 meses y el reparto por región, producto y tipo, cada uno con la pregunta de negocio que responde. Sin mes, usa el último mes completo con datos; si el mes no tiene datos, responde con los meses que sí hay. Las tarjetas "Dashboards recomendados" del reporte vacío usan `POST /api/paquetes` (sin IA). En el frontend, cada gráfico trae además una lectura automática ("Biobío concentra el 63 % del total") calculada con sus propios datos (`frontend/src/lib/lectura.js`), y la guía "Cómo pedir un buen reporte" se abre con el botón ? del chat.

### Módulo "Proyecciones" (pantalla `/proyecciones`)

La pantalla muestra la conclusión en una frase (a la baja, al alza o estable), los 3 meses proyectados con su rango, el gráfico de los últimos 2 años y "¿Qué tan confiable es?": cuánto se equivocó el pronóstico de cada uno de los últimos 6 meses, hecho solo con los datos anteriores (`acierto` en la respuesta). Si los últimos meses cayeron de golpe (posible carga incompleta), la confianza no pasa de "Media". No hay botón para recalcular: se calcula con los datos de la base al abrirla y vuelve a calcularse sola cada 5 minutos mientras está abierta.

`GET /api/proyecciones` lista las series que el usuario puede proyectar (solo métricas `si`, de sus áreas, y nunca cuotas). Las recomendadas van primero, con la decisión que apoyan (`catalogo.PROYECCIONES`): cantidad de siniestros y monto denunciado, prima directa y retenida neta, y pólizas emitidas y monto asegurado. `POST /api/proyecciones` arma el plan en el backend (toda la historia, por mes) y devuelve la serie con su proyección; desde el módulo se puede agregar al reporte del chat y guardarla en un dashboard.

## Dashboards compartidos

Un dashboard guarda los **planes** de sus gráficos, no los datos. Al abrirlo, el backend vuelve a ejecutar cada plan con los permisos de quien lo mira: si un gráfico es de un área que esa persona no puede consultar, se muestra bloqueado. Las carpetas funcionan como repositorios: el propietario agrega miembros como lector o editor, y `NUM_VERSION` evita que dos editores se pisen los cambios.

En el copiloto, el módulo **Carpetas y compartidos** del menú lateral muestra las carpetas propias y las compartidas con el usuario, con sus dashboards a un clic; desde ahí también se crea una carpeta o se comparte. Cada gráfico guarda su título (editable con el lápiz o con doble clic; vacío vuelve al automático, por ejemplo «Monto pagado por región»). Si un gráfico viejo del chat ya no calza con el catálogo, al guardar o exportar se deja fuera y se avisa.

El propietario también puede dar a un miembro un rol distinto en un dashboard puntual (botón **Permisos** del dashboard): por ejemplo, un lector de la carpeta que edita solo "Siniestros Q4". Quitar a alguien de la carpeta borra esas excepciones.

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
   Para recuperar contraseñas por correo: ejecutar `db/sqlserver/22_RECUPERACION_CLAVE.sql`, registrar el correo de cada usuario en `seguridad.SEG_USUARIO.DESC_CORREO` y completar las variables `SMTP_*` de `.env`. Sin `SMTP_HOST`, el enlace se muestra en la consola del backend.
   Para guardar y compartir dashboards: ejecutar `db/sqlserver/25_CREATE_DASHBOARDS.sql` y luego `26_DASHBOARD_PERMISO.sql`.
   Para la demo, `python demo_carpetas.py` (con el backend corriendo) deja dos carpetas compartidas de ejemplo: «Comité de Siniestros» de `USR_ADMIN` (con `USR_SIN` como editor y `USR_FIN` como lector, que además edita el dashboard «Resumen ejecutivo») y «Primas y comisiones» de `USR_FIN`, compartida con `USR_ADMIN`.
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
4. Que el Excel importado se guarde en la BD (hoy, en modo demo, queda en el navegador).
