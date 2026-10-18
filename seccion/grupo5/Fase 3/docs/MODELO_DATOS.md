BI Ruta Smart - Modelo de Datos
1. Objetivo
Diseñar una base de datos ficticia para BI Ruta Smart inspirada en una arquitectura de Data Warehouse, manteniendo un alcance simple, realista y posible de implementar dentro del proyecto Capstone.

La base de datos permitirá demostrar cómo BI Ruta Smart podrá:

Recibir una solicitud escrita por un usuario.
Identificar el área de negocio relacionada con la solicitud.
Validar qué información puede consultar el usuario.
Identificar las tablas y columnas disponibles.
Generar una consulta SQL.
Obtener los datos desde SQL Server.
Enviar los resultados a la aplicación web.
Mostrar filtros, tablas de detalle y posteriormente visualizaciones.
2. Base de datos
Nombre:

DB_BI_RUTA_SMART

Motor:

SQL Server

La base de datos será completamente ficticia y no utilizará información real de empresas, clientes ni personas.

3. Dominios de negocio
La primera versión de BI Ruta Smart contará con tres dominios principales.

SIN - Siniestros
Contendrá información relacionada con siniestros.

Ejemplos:

Siniestros.
Estados.
Pagos.
Reservas.
Recuperos.
Ejemplo de solicitud:

"Quiero ver los siniestros abiertos por región."

FIN - Finanzas
Contendrá información financiera.

Ejemplos:

Primas.
Pagos.
Comisiones.
Montos pendientes.
Movimientos financieros.
Ejemplo de solicitud:

"Quiero ver las primas pendientes por producto."

SEG - Seguros
Contendrá información relacionada con producción y cartera.

Ejemplos:

Pólizas.
Productos.
Clientes.
Vigencias.
Cartera.
Ejemplo de solicitud:

"Quiero ver las pólizas vigentes por producto."

4. Capas de información
La base de datos estará organizada mediante diferentes schemas.

ods

La capa ODS contendrá información integrada y preparada para ser utilizada por otros procesos.

Ejemplos futuros:

ods.ODS_SIN_SINIESTRO
ods.ODS_FIN_PRIMA
ods.ODS_SEG_SEGURO
DIM
Schema:

dim

La capa DIM estará orientada a consultas analíticas y generación de dashboards.

En esta capa podrán existir dimensiones compartidas como:

Tiempo.
Producto.
Región.
Cliente.
Póliza.
También existirán tablas de hechos relacionadas con cada dominio.

META
Schema:

meta

Esta capa será especialmente importante para BI Ruta Smart.

Contendrá información descriptiva sobre:

Tablas disponibles.
Columnas disponibles.
Relaciones entre tablas.
Dominio al que pertenece cada tabla.
Descripción funcional de los datos.
Información que puede utilizar la inteligencia artificial.
Tablas propuestas:

meta.MET_TABLA
meta.MET_COLUMNA
meta.MET_RELACION
SEGURIDAD
Schema:

seguridad

Esta capa administrará:

Usuarios.
Dominios.
Accesos de cada usuario.
Tablas:

seguridad.SEG_DOMINIO
seguridad.SEG_USUARIO
seguridad.SEG_USUARIO_DOMINIO
5. Modelo de seguridad
BI Ruta Smart deberá restringir la información disponible dependiendo del usuario.

Los usuarios ficticios iniciales serán:

USR_SIN
USR_FIN
USR_SEG
USR_ADMIN
Los dominios serán:

SIN
FIN
SEG
Las relaciones iniciales serán:

USR_SIN -> SIN

USR_FIN -> FIN

USR_SEG -> SEG

USR_ADMIN -> SIN

USR_ADMIN -> FIN

USR_ADMIN -> SEG

6. Relación de seguridad
El modelo será:

SEG_USUARIO | | 1:N | SEG_USUARIO_DOMINIO | | N:1 | SEG_DOMINIO

Esto permitirá que un usuario pueda tener acceso a uno o varios dominios.

Ejemplo:

USR_FIN solamente podrá consultar información relacionada con FIN.

USR_SIN solamente podrá consultar información relacionada con SIN.

USR_ADMIN podrá consultar los tres dominios.

7. Control de acceso en BI Ruta Smart
Cuando un usuario realice una solicitud, el sistema deberá seguir conceptualmente este proceso:

Identificar al usuario.
Consultar los dominios autorizados.
Interpretar la solicitud.
Identificar qué dominio necesita la consulta.
Verificar si el usuario tiene autorización.
Obtener solamente los metadatos permitidos.
Generar la consulta SQL.
Validar la consulta.
Ejecutar la consulta sobre SQL Server.
Enviar el resultado al frontend.
Ejemplo:

Usuario:

USR_SIN

Solicitud:

"Quiero ver las primas por producto."

Dominio requerido:

FIN

Resultado esperado:

Acceso no autorizado al dominio FIN.

8. Metadatos
La inteligencia artificial no deberá depender solamente del nombre de las tablas.

Se construirá un catálogo de metadatos para explicar el significado de la información disponible.

MET_TABLA
Permitirá documentar:

Schema.
Tabla.
Dominio.
Capa.
Descripción.
Disponibilidad para la IA.
Ejemplo:

ODS_SIN_SINIESTRO

Dominio:

SIN

Descripción:

Información relacionada con los siniestros registrados.

MET_COLUMNA
Permitirá documentar las columnas.

Ejemplo:

Tabla:

ODS_SIN_SINIESTRO

Columna:

MNT_PAGADO

Descripción:

Monto pagado asociado al siniestro.

MET_RELACION
Permitirá documentar cómo se relacionan las diferentes tablas.

Ejemplo:

FT_SIN_COSTO_SINIESTRO.ID_PRODUCTO

se relaciona con:

LK_PRODUCTO.ID_PRODUCTO

9. Dominios de datos futuros
SEG - Seguros
Tablas principales propuestas:

ODS_SEG_SEGURO
FT_SEG_CARTERA
Información:

Póliza.
Ítem asegurado.
Producto.
Cliente.
Región.
Estado.
Vigencia.
FIN - Finanzas
Tablas principales propuestas:

ODS_FIN_PRIMA
FT_FIN_PRIMA
Información:

Prima.
Comisión.
Prima pagada.
Prima pendiente.
Fecha del movimiento.
Producto.
Póliza.
SIN - Siniestros
Tablas principales propuestas:


ODS_SIN_SINIESTRO
ODS_SIN_MOVIMIENTO_SINIESTRO
FT_SIN_COSTO_SINIESTRO
Información:

Siniestro.
Estado.
Fecha de ocurrencia.
Reserva.
Pago.
Recupero.
Producto.
Póliza.
Región.
10. Aplicación BI Ruta Smart
BI Ruta Smart será una aplicación web.

El frontend del proyecto utilizará:

React.
Vite.
La aplicación permitirá que el usuario escriba en lenguaje natural qué información necesita.

Ejemplo:

"Quiero ver los siniestros pagados por región durante el año."

La aplicación enviará la solicitud al backend.

11. Backend
El backend será responsable de conectar la aplicación con:

SQL Server.
Seguridad.
Metadatos.
Inteligencia artificial.
Las principales responsabilidades serán:

Recibir la solicitud desde React.
Identificar al usuario.
Consultar sus permisos.
Recuperar los metadatos autorizados.
Enviar el contexto permitido al modelo de inteligencia artificial.
Obtener una definición de la consulta.
Generar o validar SQL.
Ejecutar la consulta.
Devolver los resultados al frontend.
La tecnología exacta del backend se definirá durante el desarrollo.

Python es actualmente una de las alternativas consideradas.

12. Frontend
El frontend será desarrollado con React y Vite.

En la primera versión la interfaz será sencilla.

El usuario tendrá principalmente:

Un cuadro de texto.
Un botón para generar el dashboard.
Una sección donde se mostrará el resultado.
Ejemplo:

¿Qué necesitas analizar?

"Mostrar los siniestros abiertos por región."

[Generar Dashboard]

13. Dashboard inicial
El MVP se enfocará principalmente en:

Filtros.
Tabla de detalle.
Ejemplo:

Filtros:

Fecha.
Producto.
Región.
Estado.
Detalle:

Número de siniestro.
Póliza.
Fecha.
Producto.
Región.
Estado.
Monto.
14. Evolución futura de los dashboards
Una vez que el funcionamiento básico esté correcto se podrán incorporar:

Gráficos de barras.
Gráficos de líneas.
Gráficos circulares.
Indicadores.
Tarjetas.
Diferentes visualizaciones según la solicitud.
La aplicación actualmente incluye Recharts como librería disponible para desarrollar gráficos dentro de React.

15. Flujo general de BI Ruta Smart
El flujo esperado será:

Usuario | v React + Vite | v Backend | +----------------------+ | | v v Seguridad Metadatos | | +----------+-----------+ | v Inteligencia Artificial | v Validación SQL | v SQL Server | v Datos | v React + Vite | v Dashboard Web

16. Estado actual
Base de datos
DB_BI_RUTA_SMART

Schemas creados
stg
ods
dim
meta
seguridad
Dominios
SIN - Siniestros
FIN - Finanzas
SEG - Seguros
Tablas de seguridad
seguridad.SEG_DOMINIO
seguridad.SEG_USUARIO
seguridad.SEG_USUARIO_DOMINIO
17. Próximos pasos
El orden de construcción será:

Completar seguridad.
Crear MET_TABLA.
Crear MET_COLUMNA.
Crear MET_RELACION.
Diseñar las tablas del dominio SEG.
Diseñar las tablas del dominio FIN.
Diseñar las tablas del dominio SIN.
Crear datos ficticios.
Validar consultas SQL manualmente.
Construir la integración entre backend y SQL Server.
Integrar inteligencia artificial.
Conectar el backend con React.
Mostrar tablas y filtros dinámicamente.
Incorporar gráficos como evolución del MVP.