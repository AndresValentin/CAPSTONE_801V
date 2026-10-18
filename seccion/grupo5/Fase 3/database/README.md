Base de datos BI Ruta Smart
Motor
SQL Server.

Base de datos
DB_BI_RUTA_SMART.

Orden de ejecución
Ejecutar los scripts una sola vez y en el siguiente orden:

00_CREATE_DATABASE.sql
01_CREATE_SCHEMAS.sql
02_CREATE_SEG_DOMINIO.sql
03_CREATE_SEG_USUARIO.sql
04_CREATE_SEG_USUARIO_DOMINIO.sql
05_CREATE_MET_TABLA.sql
06_CREATE_MET_COLUMNA.sql
07_CREATE_MET_RELACION.sql
08_CREATE_ODS_SEG_CLIENTE.sql
09_CREATE_ODS_SEG_SEGURO.sql
10_CREATE_ODS_FIN_PRIMA.sql
11_CREATE_ODS_SIN_SINIESTRO.sql
12_INSERT_DATA_DEMO.sql
13_INSERT_METADATA.sql
Consideraciones
Los scripts deben ejecutarse en orden debido a las dependencias entre tablas.
Los archivos 12_INSERT_DATA_DEMO.sql y 13_INSERT_METADATA.sql están diseñados para ejecutarse una sola vez.
No se deben volver a ejecutar sobre una base ya poblada.
Todos los datos incluidos son sintéticos y se utilizan exclusivamente para el desarrollo del proyecto.
Las credenciales y cadenas de conexión no deben almacenarse en Git.