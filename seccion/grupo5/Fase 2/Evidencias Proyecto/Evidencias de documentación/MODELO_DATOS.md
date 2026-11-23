# BI Copilot - Modelo de Datos

## 1. Objetivo

El objetivo es construir la base de datos de BI Ruta Smart, organizando la información de seguros, finanzas y siniestros junto con los permisos, metadatos y relaciones necesarios para realizar consultas.

La base de datos permite a BI Ruta Smart:

- Recibir una solicitud escrita por un usuario.
- Identificar el dominio de negocio relacionado con la solicitud.
- Validar qué información puede consultar el usuario.
- Identificar las tablas, columnas y relaciones disponibles.
- Generar y validar una consulta SQL.
- Obtener los datos desde SQL Server.
- Enviar los resultados a la aplicación web.
- Mostrar filtros, tablas de detalle y, posteriormente, visualizaciones.


---

## 2. Base de datos

- **Motor:** SQL Server
- **Base de datos:** `DB_BI_RUTA_SMART`

La base se organiza mediante schemas para separar las responsabilidades técnicas y funcionales.

---

## 3. Dominios de negocio

### 3.1 SIN - Siniestros

Contiene información relacionada con siniestros, estados y montos asociados.

Ejemplos de información:

- Siniestros.
- Fecha de ocurrencia y denuncia.
- Estado del siniestro.
- Monto denunciado.
- Reserva.
- Pago.
- Recupero.

Ejemplo de solicitud:

> Quiero ver los siniestros abiertos por región.

### 3.2 FIN - Finanzas

Contiene información relacionada con movimientos de prima y comisiones.

Ejemplos de información:

- Emisiones.
- Anulaciones.
- Prima.
- Comisión.
- Estado de pago.
- Fecha de movimiento y pago.

Ejemplo de solicitud:

> Quiero ver las primas pendientes por producto.

### 3.3 SEG - Seguros

Contiene información relacionada con clientes, pólizas, certificados e ítems asegurados.

Ejemplos de información:

- Clientes.
- Pólizas.
- Certificados.
- Productos.
- Ítems asegurados.
- Vigencias.
- Estado de póliza.
- Monto asegurado.

Ejemplo de solicitud:

> Quiero ver las pólizas vigentes por producto.

---

## 4. Capas y schemas

### 4.1 ODS

Schema: `ods`

La capa ODS contiene información integrada y relacionada para los procesos del proyecto.

Tablas actuales:

- `ods.ODS_SEG_CLIENTE`
- `ods.ODS_SEG_SEGURO`
- `ods.ODS_FIN_PRIMA`
- `ods.ODS_SIN_SINIESTRO`

### 4.2 DIM

Schema: `dim`

La capa DIM concentrará el modelo analítico mediante dimensiones y tablas de hechos. La información será procesada desde ODS mediante procedimientos almacenados.

Componentes previstos:

- Dimensión de tiempo.
- Dimensión de producto.
- Dimensión de región.
- Dimensión de cliente.
- Dimensión de póliza.
- Hechos de cartera.
- Hechos de prima.
- Hechos de siniestros.

### 4.3 META

Schema: `meta`

La capa META contiene el catálogo funcional utilizado por el backend y la inteligencia artificial para interpretar el modelo de datos.

Tablas:

- `meta.MET_TABLA`
- `meta.MET_COLUMNA`
- `meta.MET_RELACION`

### 4.4 SEGURIDAD

Schema: `seguridad`

La capa SEGURIDAD administra usuarios, dominios y autorizaciones funcionales.

Tablas:

- `seguridad.SEG_DOMINIO`
- `seguridad.SEG_USUARIO`
- `seguridad.SEG_USUARIO_DOMINIO`

---

## 5. Modelo de seguridad

### 5.1 Usuarios iniciales

- `USR_SIN`
- `USR_FIN`
- `USR_SEG`
- `USR_ADMIN`

### 5.2 Dominios

- `SIN` - Siniestros
- `FIN` - Finanzas
- `SEG` - Seguros

### 5.3 Asignaciones iniciales

- `USR_SIN` → `SIN`
- `USR_FIN` → `FIN`
- `USR_SEG` → `SEG`
- `USR_ADMIN` → `SIN`
- `USR_ADMIN` → `FIN`
- `USR_ADMIN` → `SEG`

### 5.4 Relación

```text
SEG_USUARIO
     1
     |
     N
SEG_USUARIO_DOMINIO
     N
     |
     1
SEG_DOMINIO
```

La tabla intermedia permite que un usuario tenga acceso a uno o varios dominios y evita repetir una misma asignación.

### 5.5 Flujo de autorización

1. Identificar al usuario.
2. Verificar que el usuario esté activo.
3. Consultar los dominios autorizados.
4. Identificar el dominio requerido por la solicitud.
5. Verificar si el usuario tiene permiso para consultar ese dominio.
6. Recuperar solamente las tablas y columnas autorizadas.
7. Generar y validar una consulta de solo lectura.
8. Ejecutar la consulta.
9. Devolver el resultado al frontend.

Ejemplo:

```text
Usuario: USR_SIN
Solicitud: Quiero ver las primas por producto.
Dominio requerido: FIN
Resultado: Acceso no autorizado al dominio FIN.
```

---

## 6. Modelo de metadatos

Los metadatos describen el modelo sin depender únicamente de nombres técnicos.

### 6.1 MET_TABLA

Documenta:

- Schema.
- Tabla.
- Dominio.
- Capa.
- Descripción funcional.
- Disponibilidad para IA.
- Estado activo.

Ejemplo:

```text
Tabla: ODS_SIN_SINIESTRO
Dominio: SIN
Descripción: Información de siniestros asociados a ítems asegurados.
```

### 6.2 MET_COLUMNA

Documenta:

- Tabla a la que pertenece la columna.
- Nombre de columna.
- Tipo de dato.
- Descripción funcional.
- Si es llave.
- Si es medida.
- Si puede utilizarse como filtro.
- Disponibilidad para IA.
- Estado activo.

Ejemplo:

```text
Tabla: ODS_SIN_SINIESTRO
Columna: MNT_PAGADO
Descripción: Monto pagado asociado al siniestro.
Medida: Sí
Filtro: No
```

### 6.3 MET_RELACION

Documenta cómo se conectan las tablas y proporciona rutas de unión autorizadas para la generación de consultas.

Relaciones actuales:

```text
ODS_SEG_SEGURO.ID_CLIENTE
N:1
ODS_SEG_CLIENTE.ID_CLIENTE
```

```text
ODS_FIN_PRIMA.ID_ITEM
N:1
ODS_SEG_SEGURO.ID_ITEM
```

```text
ODS_SIN_SINIESTRO.ID_ITEM
N:1
ODS_SEG_SEGURO.ID_ITEM
```

### 6.4 Diferencia entre FK y MET_RELACION

- Una **Foreign Key** protege la integridad física de SQL Server.
- `MET_RELACION` explica al backend y a la IA cómo deben conectarse las tablas.

---

## 7. Modelo relacional ODS

```text
ODS_SEG_CLIENTE
    ID_CLIENTE
        |
        | 1:N
        v
ODS_SEG_SEGURO
    ID_ITEM
        |
        +--------------------------+
        |                          |
        | 1:N                      | 1:N
        v                          v
ODS_FIN_PRIMA              ODS_SIN_SINIESTRO
    ID_ITEM                    ID_ITEM
```

### 7.1 ODS_SEG_CLIENTE

Grano:

> Una fila por cliente.

Identificación:

- Técnica: `ID_CLIENTE`
- Funcional: `COD_CLIENTE`

Información principal:

- Tipo de cliente.
- Segmento.
- Región del cliente.

### 7.2 ODS_SEG_SEGURO

Grano:

> Una fila por ítem o certificado asegurado dentro de una póliza.

Identificación:

- Técnica: `ID_ITEM`
- Funcional: `COD_POLIZA + COD_CERTIFICADO`

Ejemplo:

```text
POL000001 / Certificado 1
POL000001 / Certificado 2
```

Información principal:

- Cliente.
- Producto.
- Región del ítem asegurado.
- Fecha de emisión.
- Inicio y fin de vigencia.
- Estado de póliza.
- Monto asegurado.

### 7.3 ODS_FIN_PRIMA

Grano:

> Una fila por movimiento de prima asociado a un ítem asegurado.

Identificación:

- Técnica: `ID_MOVIMIENTO_PRIMA`
- Funcional dentro del ítem: `ID_ITEM + NRO_MOVIMIENTO`

Ejemplo:

```text
Movimiento 1: EMISION
Movimiento 2: ANULACION
```

`MNT_PRIMA` puede ser negativo cuando el movimiento representa una anulación. `MNT_COMISION` no admite valores negativos.

### 7.4 ODS_SIN_SINIESTRO

Grano:

> Una fila por siniestro asociado a un ítem asegurado.

Identificación:

- Técnica: `ID_SINIESTRO`
- Funcional: `COD_SINIESTRO`

Información principal:

- Fecha de ocurrencia.
- Fecha de denuncia.
- Tipo de siniestro.
- Estado.
- Monto denunciado.
- Reserva.
- Pago.
- Recupero.

---

## 8. Reglas de integridad

Las tablas utilizan constraints para proteger la calidad de los datos.

### 8.1 Primary Key

Evita duplicados técnicos e identifica cada fila.

### 8.2 Foreign Key

Evita registros huérfanos y garantiza que las relaciones apunten a registros existentes.

### 8.3 Unique

Protege identificadores funcionales, por ejemplo:

- Código de dominio.
- Código de usuario.
- Código de cliente.
- Póliza + certificado.
- Ítem + número de movimiento.
- Código de siniestro.

### 8.4 Check

Valida reglas como:

- Fecha final de vigencia igual o posterior a la fecha inicial.
- Número de movimiento mayor que cero.
- Comisión no negativa.
- Fecha de denuncia igual o posterior a la ocurrencia.
- Montos de siniestro no negativos.

### 8.5 Default y Not Null

Los valores por defecto junto con `NOT NULL` reducen nulos innecesarios y simplifican las consultas. Los campos donde la ausencia tiene significado, como una fecha de pago pendiente, pueden conservar `NULL`.

---

## 9. Datos iniciales

La carga inicial incorpora:

- 10 clientes.
- 11 ítems asegurados.
- 12 movimientos de prima.
- 8 siniestros.
- 4 tablas registradas en metadata.
- 37 columnas registradas en metadata.
- 3 relaciones registradas en metadata.

El conjunto inicial permite validar relaciones, permisos, consultas y resultados antes de incorporar nuevas fuentes de información.

---

## 10. Aplicación BI Ruta Smart

BI Ruta Smart será una aplicación web.

### 10.1 Frontend

Tecnologías:

- React.
- Vite.
- Recharts para la representación de visualizaciones.

Responsabilidades:

- Recibir la solicitud del usuario.
- Enviar la solicitud al backend.
- Mostrar el título, filtros, columnas y datos recibidos.
- Representar inicialmente una tabla de detalle.
- Incorporar gráficos dinámicos en la interfaz.

### 10.2 Backend

Responsabilidades:

- Recibir la solicitud desde React.
- Identificar al usuario.
- Consultar permisos por dominio.
- Recuperar metadata autorizada.
- Preparar el contexto para la inteligencia artificial.
- Generar o validar SQL de solo lectura.
- Ejecutar la consulta en SQL Server.
- Devolver una respuesta estructurada al frontend.

El backend se mantiene desacoplado del frontend y centraliza la integración con SQL Server, la seguridad y los metadatos.

### 10.3 Contrato conceptual

Solicitud:

```json
{
  "usuario": "USR_SIN",
  "pregunta": "Mostrar los siniestros abiertos por región"
}
```

Respuesta:

```json
{
  "success": true,
  "dashboard": {
    "title": "Siniestros abiertos por región",
    "domain": "SIN",
    "filters": [],
    "columns": [],
    "data": []
  }
}
```

La inteligencia artificial interpreta la solicitud, el backend aplica las autorizaciones y validaciones, SQL Server devuelve los datos y React presenta el resultado.

---

## 11. Interfaz analítica

La primera versión funcional incluye:

- Cuadro de solicitud en lenguaje natural.
- Validación del dominio autorizado.
- Filtros.
- Tabla de detalle.

Posibles filtros:

- Fecha.
- Producto.
- Región.
- Estado.
- Póliza.
- Certificado.

Posibles campos de detalle:

- Cliente.
- Póliza.
- Certificado.
- Producto.
- Siniestro.
- Fecha.
- Región.
- Estado.
- Montos.

Visualizaciones contempladas:

- Gráficos de barras.
- Gráficos de líneas.
- Gráficos circulares.
- Indicadores.
- Tarjetas.
- Visualizaciones dinámicas mediante Recharts.

---

## 12. Flujo general

```text
Usuario
   |
   v
React + Vite
   |
   v
Backend / API
   |
   +--------------------------+
   |                          |
   v                          v
Seguridad                  Metadata
   |                          |
   +-------------+------------+
                 |
                 v
        Inteligencia artificial
                 |
                 v
          Validación SQL
                 |
                 v
            SQL Server
                 |
                 v
               Datos
                 |
                 v
            Backend / API
                 |
                 v
          React + Vite
                 |
                 v
          Dashboard web
```

---

## 13. Estado de implementación

### Implementado

- Base de datos `DB_BI_RUTA_SMART`.
- Schemas `ods`, `dim`, `meta` y `seguridad`.
- Modelo de seguridad.
- Usuarios y dominios iniciales.
- Tablas de metadata.
- Tablas ODS de clientes, seguros, primas y siniestros.
- Constraints de integridad.
- Datos iniciales para validación funcional.
- Metadata de tablas, columnas y relaciones.
- Script de validación de instalación.
- Scripts versionados para reconstruir la base.

### Siguiente etapa

- Definir el modelo dimensional.
- Crear dimensiones y tablas de hechos.
- Crear procedimientos almacenados ODS → DIM.
- Registrar la capa DIM en metadata.
- Configurar la conexión segura entre el backend y SQL Server.
- Implementar seguridad por dominio en el backend.
- Integrar el servicio de inteligencia artificial.
- Integrar el backend con la aplicación React.
- Generar filtros y tablas a partir de la respuesta del backend.
- Incorporar gráficos dinámicos en la interfaz.

---

## 14. Instalación

Los scripts de base de datos deben ejecutarse en el orden indicado en `database/README.md`.

La secuencia actual comprende:

1. Creación de la base.
2. Creación de schemas.
3. Seguridad.
4. Metadata.
5. ODS.
6. Carga inicial de datos.
7. Carga del catálogo de metadata.
8. Validación de la instalación.

Los scripts de carga inicial deben ejecutarse una sola vez sobre una base vacía. El script de validación puede ejecutarse nuevamente porque contiene únicamente consultas de lectura.
