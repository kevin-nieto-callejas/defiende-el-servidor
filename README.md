# Autonomous Rally

Proyecto final de MLOps, Universidad Externado de Colombia (2026-II). Un agente de aprendizaje por refuerzo
completa un circuito inspirado en Mónaco pasando los checkpoints en orden, con seco, lluvia y perturbaciones.
Todo experimento se puede consultar, reproducir y restaurar.

| Entrega | Dónde |
|---|---|
| Web publicada | https://autonomous-rally.vercel.app (modo replay hasta publicar la API) |
| Ficha del ambiente y niveles | [docs/ambiente-v0.1.md](docs/ambiente-v0.1.md) |
| Experimentos (MLflow) | https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments |
| Datos y modelos (DVC) | https://dagshub.com/kevin-nieto-callejas/autonomous-rally |
| Modelo publicado | https://huggingface.co/Kevinnieto0001/autonomous-rally-ppo |
| Manifiestos de cada versión | [manifests/](manifests/) |
| Criterios de selección | [configs/seleccion.yaml](configs/seleccion.yaml) |

## Arquitectura

```
Git + DVC ──► Entrenamiento en PC (dvc repro, orquestado por Prefect)
                 │
                 ├─ MLflow: runs, métricas, registro de modelos
                 └─ manifests/: pesos, SHA-256, contrato, ambiente, resultados
                          │
                          ▼
Vercel (web/: Vite, TypeScript, three.js) ──HTTPS──► API (FastAPI): simula con el mismo Python del entrenamiento
```

Python es la autoridad del mundo: el navegador solo dibuja lo que la API simula. La velocidad de animación
no cambia las reglas. Cada respuesta dice qué modelo, ambiente y modo la produjo.

```
src/rally/      ambiente, pista, pilotos, agentes, pipeline, API y selección
src/rally/static/  visor 3D (lo comparten `rally web` y la web de Vercel)
web/            aplicación Vite + TypeScript: catálogo, evaluación y comparación
pipelines/      flujo de Prefect
manifests/      identidad de cada modelo y catálogo
configs/        criterios fijados de selección
deploy/api/     contenedor de la API
tests/          reglas, trampas, agentes, API y selección
```

## Instalación

Probado con Python 3.14 en WSL Ubuntu y Node 22.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # incluye PyTorch CPU
.venv/bin/pip install -e .
.venv/bin/pytest
cp .env.example .env                          # solo para publicar; ver variables abajo
dvc pull                                      # datos y modelos (repo público: no pide token)
```

| Variable | Dónde | Para qué |
|---|---|---|
| `HF_TOKEN` | `.env` | Publicar en Hugging Face |
| `DAGSHUB_TOKEN` | `.env` | Copiar MLflow a DagsHub |
| `VITE_API_BASE_URL` | Vercel | URL HTTPS de la API (pública) |
| `RALLY_ORIGENES` | API | Orígenes permitidos por CORS |
| `RALLY_MODELOS` | API | Carpeta de pesos por SHA-256 |

## Ejecutar

```bash
rally api                      # API en http://127.0.0.1:8000
cd web && npm ci && npm run dev   # web en http://localhost:5173
rally web                      # visor local con entrenamiento en vivo, http://localhost:8765
```

## Reproducir

```bash
dvc repro                      # datos → qlearning / ppo → evaluar → registrar → generalizacion
dvc metrics show
rally manifiesto               # regenera manifests/ desde las etiquetas de git
rally semillas ppo 1 2         # contraste de finalistas con otras semillas
```

Pipeline completo con Prefect, en un entorno aparte para no tocar el del entrenamiento:

```bash
python3 -m venv ~/.venvs/rally-flujo && ~/.venvs/rally-flujo/bin/pip install prefect pyyaml
~/.venvs/rally-flujo/bin/python pipelines/flujo.py --candidato ppo-modelo-v5 --tipo ppo
~/.venvs/rally-flujo/bin/python pipelines/flujo.py --rollback "motivo"
```

Valida el perfil, corre las pruebas, entrena, registra, aplica los criterios, promueve, publica el catálogo y
comprueba la versión que la API realmente sirve. Registrar un candidato no lo promueve.

Para recuperar un modelo antiguo: `git checkout <etiqueta> && dvc checkout`, o cárgalo desde el catálogo. Los de
familias anteriores corren con un adaptador; `runs/validar_historicos.py` comparó sus resultados con los guardados.

## Modelos

Son dos agentes: **Q-learning** con tabla y **PPO** con red neuronal. Experto, prudente, maestro y aleatoria
son pilotos de referencia.

| Versión | Hipótesis | Resultado | Decisión |
|---|---|---|---|
| `modelo-v1` | Primer modelo en seco | Seco 100 %, lluvia 0 % | Reemplazado |
| `modelo-v2` | Un sensor de agarre ayuda con lluvia | Seco 100 %, lluvia 0 % | Reemplazado |
| `experimento-v3` | Practicar con lluvia e imitar | 0 % en ambos | Rechazado |
| `modelo-v4` | DAgger corrige los errores | 100 % / 100 %, pero falla en extremos | Aceptado |
| `modelo-qlearning-v6` | Imitación tabular | 60 % / 15 % | Reemplazado |
| `modelo-v5` (semilla 0) | Conocer el carro y practicar todos los deslizadores con ruido | 100 % / 100 %, 75.9 s y 92.0 s; 98.5 % en extremos | Candidato |
| **`ppo-modelo-v5-s1`** | Misma configuración, semilla 1 | **100 % / 100 %**, 68.6 s y 89.3 s; 100 % en extremos | **Recomendado** |
| `modelo-qlearning-v7` | Ver el margen de frenada y medir el pedal en m/s² | 87 % / 81 %; 64.8 % en extremos | Reemplazado |
| `modelo-qlearning-v8` (semilla 0) | Practicar con carros lentos y ruido | 99 % / 100 %; 85.0 % en extremos | Candidato |
| **`qlearning-modelo-qlearning-v8-s1`** | Misma configuración, semilla 1 | **100 % / 100 %**, 81.0 s y 106.9 s; 85.9 % en extremos | **Elegido de su agente** |

Resultados: seco / lluvia con 100 vueltas por condición. Las semillas 1 y 2 están en `finalistas/`, versionadas con
DVC. Los detalles, las pruebas de extremos y los límites están en la ficha. Limitación principal: hay un solo
circuito.

**Test reservado** (`rally test-final`, una sola corrida, semillas fuera del repositorio):
PPO semilla 1 dio 100 % / 100 % y 99.9 % en extremos; Q-learning semilla 1, 99 % / 99 % y 84.8 %. Resultado en
[metrics/test-final.json](metrics/test-final.json).

La evidencia del flujo de Prefect y del rollback de v5 a v4 y de vuelta está en
[docs/evidencia/flujo/](docs/evidencia/flujo/) y [manifests/historial.json](manifests/historial.json).

## Publicar

```bash
.venv/bin/python deploy/api/empaquetar.py ../rally-space   # carpeta para el Space, con pesos verificados
```

En Vercel: Root Directory `web`, Build `npm run build`, Output `dist`, y la variable `VITE_API_BASE_URL`.

## Antecedente

Este repositorio empezó con otro proyecto, conservado en [docs/defiende-el-servidor.md](docs/defiende-el-servidor.md).
