# BI Copilot

**Proyecto Capstone — Ingeniería en Informática**

**Estado:** En desarrollo  
**Dominio funcional del MVP:** Siniestros (SIN)

## Descripción del proyecto

BI Copilot es una aplicación de inteligencia de negocios que busca facilitar el análisis de información mediante consultas realizadas en lenguaje natural.

La solución utiliza inteligencia artificial para interpretar las preguntas de los usuarios y transformarlas en planes estructurados, que posteriormente son validados antes de generar consultas SQL controladas.

Los resultados se presentan mediante dashboards interactivos con indicadores, gráficos, filtros y explicaciones basadas en datos verificables.

## Objetivo

Facilitar la exploración y comprensión de datos de negocio sin exigir que los usuarios conozcan SQL ni herramientas especializadas de análisis.

## Arquitectura tecnológica

| Componente | Tecnología |
|---|---|
| Frontend | React |
| Backend | Python + FastAPI |
| Inteligencia artificial | Anthropic Claude |
| Base de datos | Microsoft SQL Server |
| Visualizaciones | Recharts |
| Gestión del proyecto | Jira |
| Control de versiones | GitHub |

## Funcionamiento previsto del MVP

1. El usuario inicia sesión y formula una pregunta en lenguaje natural.
2. Claude interpreta la solicitud y genera un plan JSON estructurado.
3. FastAPI valida el plan contra el catálogo semántico autorizado.
4. El usuario revisa y aprueba explícitamente la consulta propuesta.
5. El backend verifica la autorización y ejecuta consultas SQL de solo lectura.
6. React presenta los resultados mediante un dashboard analítico.
7. El usuario puede explorar filtros autorizados y recuperar dashboards guardados.

## Alcance del MVP

El dominio de análisis principal es **Siniestros (SIN)**, utilizando datos sintéticos almacenados en SQL Server.

La solución contempla controles de acceso, aprobación humana, trazabilidad técnica, métricas autorizadas y visualizaciones basadas en resultados verificables.

## Equipo del proyecto

| Integrante | Responsabilidad |
|---|---|
| Ignacio | Gestión, planificación, requisitos y evidencias |
| Felipe | Base de datos, modelo SQL y validación analítica |
| Valentín | Frontend, backend e integraciones |
