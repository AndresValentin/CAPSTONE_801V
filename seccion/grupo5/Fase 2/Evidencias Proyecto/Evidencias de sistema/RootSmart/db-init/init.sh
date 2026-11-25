#!/usr/bin/env bash
# Crea DB_BI_RUTA_SMART ejecutando los scripts SQL en orden. Corre una sola vez:
# si la base ya existe, no hace nada (los scripts de datos no se pueden repetir).
set -euo pipefail

SQL="/opt/mssql-tools18/bin/sqlcmd -S db -U sa -P $MSSQL_SA_PASSWORD -C -b -f 65001"

existe=$($SQL -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN DB_ID('DB_BI_RUTA_SMART') IS NULL THEN 0 ELSE 1 END")
if [ "$(echo "$existe" | tr -d '[:space:]')" = "1" ]; then
  echo "DB_BI_RUTA_SMART ya existe: no se vuelve a cargar."
  exit 0
fi

ejecutar() {
  echo ">> $1"
  $SQL -i "$1" -o /dev/null
}

# 1. Modelo de datos (Levantamiento Database): estructura, datos demo, metadatos,
#    modelo de cuotas y volumen sintético. Los scripts 14, 19 y 21 solo validan.
for n in 00 01 02 03 04 05 06 07 08 09 10 11 12 13 15 16 17 18 20; do
  ejecutar /scripts/modelo/${n}_*.sql
done

# 2. Scripts del backend: auditoría, usuario bi_lector, claves, recuperación,
#    superadministrador, solicitudes de acceso y dashboards compartidos.
for n in 15 16 17 22 23 24 25 26; do
  ejecutar /scripts/backend/${n}_*.sql
done

echo "Base DB_BI_RUTA_SMART lista."
