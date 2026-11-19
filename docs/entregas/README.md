# Guía para el revisor

Dónde está cada cosa que piden el enunciado del proyecto final (30 de octubre) y la guía de entrega final
(13 de noviembre). Todo es público: no hace falta cuenta ni contraseña.

## Enlaces

| Qué | Dónde |
|---|---|
| Aplicación (web y API en la misma URL) | https://autonomous-rally.vercel.app |
| Repositorio | https://github.com/melo11miguel/defiende-el-servidor |
| Registro de experimentos (MLflow) y artefactos (DVC) | https://dagshub.com/kevin-nieto-callejas/autonomous-rally |
| Modelo recomendado publicado | https://huggingface.co/Kevinnieto0001/autonomous-rally-ppo (etiqueta `v6-s1`) |
| Presentación | [presentacion/presentacion.pdf](presentacion/presentacion.pdf) |
| Release final | Ver [Releases](https://github.com/melo11miguel/defiende-el-servidor/releases) en GitHub |

## Modelo recomendado y un modelo histórico

| | Recomendado | Histórico |
|---|---|---|
| Modelo | `ppo-modelo-v6-pistas-s1` | `ppo-modelo-v4` |
| Run en MLflow de DagsHub | `fd93bd33ad3c41f9872e8319203fccdf` | `00ca8256fb174765bbe23cdb67795303` |
| Run de origen (en el manifiesto y en la etiqueta `origen_run_id` de DagsHub) | `65771e5dc18146f9ac59caaf44214212` (GitHub Actions) | `881772cccb024f6793d776f6da977dc7` (MLflow local) |
| Versión en el registro | `rally-ppo` v7, alias `@champion` | `rally-ppo` v4 |
| Ambiente compatible | `0.4-monaco-configurable` | `0.3-monaco-lluvia` (corre con adaptador validado) |
| Etiqueta de git | `modelo-v6-pistas-s1` | `modelo-v4` |
| SHA-256 de los pesos | `1f68d191…94edf` | `4c4c8dd6…6550c` |
| Manifiesto | [ppo-modelo-v6-pistas-s1.json](../../manifests/ppo-modelo-v6-pistas-s1.json) | [ppo-modelo-v4.json](../../manifests/ppo-modelo-v4.json) |

En la web: **Catálogo** → buscar el modelo → **Cargar** o **Evaluar**. Para compararlos, marcar las dos casillas.

## Lo que pide revisar en el repositorio

| Pedido | Archivo |
|---|---|
| README: misión, arquitectura, instalación, ejecución y reproducción | [README.md](../../README.md) |
| Ficha del ambiente y tres niveles | [docs/ambiente-v0.1.md](../ambiente-v0.1.md) (niveles al principio) |
| Cuatro o más configuraciones con hipótesis, runs y estados | MLflow en DagsHub; resumen en [README.md](../../README.md#modelos) e [informe.md](informe.md#evolución-de-los-experimentos) |
| Evaluaciones por caso | [metrics/evaluacion.json](../../metrics/evaluacion.json), [metrics/generalizacion.json](../../metrics/generalizacion.json) (21 casos), [metrics/semillas*.json](../../metrics/) |
| Comparación de experimentos y finalistas | [informe.md](informe.md), [metrics/semillas-resumen.json](../../metrics/semillas-resumen.json), [experimentos/v6-pistas.md](../experimentos/v6-pistas.md) |
| Modelos recuperables: manifiestos, normalización, hashes y dependencias | [manifests/](../../manifests/) (21 en [catalogo.json](../../manifests/catalogo.json)), `models/*.dvc`, [requirements.txt](../../requirements.txt) |
| Instrucciones de evaluación y recuperación | [README.md, secciones Reproducir y Modelos](../../README.md#reproducir) |
| Pipeline | [pipelines/flujo.py](../../pipelines/flujo.py) (Prefect) y [dvc.yaml](../../dvc.yaml); evidencia en [docs/evidencia/](../evidencia/) |
| Incidente de degradación e intervención | [informe.md, sección Incidente](informe.md#incidente-degradación-e-intervención) |
| Prueba de rollback | [docs/evidencia/flujo/rollback.json](../evidencia/flujo/rollback.json) y [manifests/historial.json](../../manifests/historial.json) |
| Selección con criterios fijados antes | [configs/seleccion.yaml](../../configs/seleccion.yaml) y [manifests/decisiones.json](../../manifests/decisiones.json) |
| Test reservado (semillas fuera del repositorio) | [metrics/test-final.json](../../metrics/test-final.json), [metrics/test-final-v6-s1.json](../../metrics/test-final-v6-s1.json) |
| Informe: decisiones, resultados, límites y contribuciones de cada integrante | [informe.md](informe.md) (sección Contribuciones) |
| Segundo vehículo (moto MotoGP, 26 observaciones): ambiente, modelos y manifiestos propios | [README.md](../../README.md), [informe.md](informe.md) y `manifests/moto/`; en la web y la API con `?vehiculo=moto` / `--vehiculo moto` |
| Presupuesto utilizado y curvas de entrenamiento y evaluación | [informe.md, sección Presupuesto](informe.md#presupuesto-utilizado-y-curvas) |
| Licencias de los recursos | [docs/LICENCIAS.md](../LICENCIAS.md) |

## Limitaciones conocidas

- **Extremos combinados:** las pruebas cambian una condición a la vez. Con todos los deslizadores al extremo al mismo
  tiempo, el modelo falla.
- **La recomendada no tiene prueba en una pista que nunca vio:** la pista reservada (Sierra) se usó con la v6
  semilla 0.
- **En la URL pública, PPO corre en numpy** (Vercel no admite PyTorch); se verificó contra PyTorch, con una
  diferencia máxima de 1e-5.
- **El monitoreo es por instancia** de la función de Vercel: si se reinicia, el conteo vuelve a cero.
- **No hay control manual del carro:** la interfaz muestra aleatorio, referencia, evaluación, entrenamiento en vivo y
  replay.
- **Si la API no responde,** la web entra en modo replay y lo dice.
