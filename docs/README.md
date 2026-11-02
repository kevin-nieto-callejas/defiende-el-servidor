# Documentación

Empieza por el [resumen general](RESUMEN-GENERAL.md).

| Carpeta o archivo | Contenido |
|---|---|
| [RESUMEN-GENERAL.md](RESUMEN-GENERAL.md) | Qué se pidió, qué se hizo, cómo vamos y qué falta |
| [ambiente-v0.1.md](ambiente-v0.1.md) | Ficha del ambiente: niveles, variables, recompensa y resultados |
| [mapa-ambiente-v0.1.svg](mapa-ambiente-v0.1.svg) | Mapa del circuito |
| [entregas/](entregas/) | Informe y presentación |
| [guias/](guias/) | Cómo instalar, reproducir, colaborar y publicar |
| [registro/](registro/) | Bitácora del proyecto y registros de la corrida final |
| [evidencia/](evidencia/) | Mediciones y evidencia de Prefect y modelos históricos |
| [antecedentes/](antecedentes/) | Plan original del repositorio, que ya no aplica |

La ficha sigue en `docs/ambiente-v0.1.md` porque la actividad del curso pide esa ruta.

Fuera de `docs/`:

| Carpeta | Contenido |
|---|---|
| `src/rally/` | Ambiente, agentes, pipeline, API y selección |
| `web/` | Aplicación Vite + TypeScript para Vercel |
| `pipelines/` | Flujo de Prefect |
| `manifests/` | Identidad de cada modelo, catálogo e historial de promociones |
| `configs/` | Criterios de selección |
| `metrics/` | Resultados oficiales, semillas y test reservado |
| `finalistas.dvc` | Pesos de las semillas 1 y 2 |
| `scripts/` | Mediciones y automatización usadas en la corrida final |
| `deploy/api/` | Contenedor de la API |
| `tests/` | Pruebas automáticas |
