# Autonomous Rally: resumen general del proyecto

**Lee este archivo primero.** Explica qué se pidió, qué se hizo, cómo vamos y qué falta. Está escrito para quien
llega al proyecto sin contexto. Última actualización: 1 de noviembre de 2026.

## En 30 segundos

Es el proyecto final de MLOps de la Universidad Externado. Entrenamos un agente que da una vuelta a un circuito
inspirado en Mónaco, pasando seis checkpoints en orden, con seco, lluvia y perturbaciones. Además construimos el
ciclo completo para que cada resultado se pueda revisar, reproducir y deshacer.

| Dato | Valor |
|---|---|
| Modelo recomendado | `ppo-modelo-v5-s1` (red neuronal PPO) |
| Resultado en el test reservado | 100 % de vueltas en seco, 100 % con lluvia, 99.9 % en 19 pruebas extremas |
| Avance estimado frente a la rúbrica | Cerca del 88 % |
| Lo que más falta | Publicar la API, para evaluar en vivo desde la web |
| Web | https://autonomous-rally.vercel.app (modo replay: vueltas grabadas) |

El 88 % es una estimación del equipo según la rúbrica, no una medición.

**Nota sobre el nombre:** el repositorio se llama `defiende-el-servidor` porque empezó con otro proyecto. Ese plan
quedó guardado en [antecedentes/](antecedentes/defiende-el-servidor.md) y ya no aplica.

## Qué se pidió

El enunciado pide un ambiente de aprendizaje por refuerzo, dos agentes y un ciclo de MLOps verificable. El docente
debe poder abrir una URL, elegir un modelo histórico y evaluarlo con su ambiente compatible.

| Criterio de la rúbrica | Peso | Estado |
|---|---:|---|
| Versionamiento y recuperación | 30 % | Casi completo |
| Diseño experimental y análisis | 25 % | Casi completo |
| Pipeline, despliegue, monitoreo y rollback | 20 % | Falta la API pública |
| Ambiente y agente | 10 % | Completo |
| Defensa, informe y presentación | 15 % | Material listo; falta ensayar y completar datos del equipo |

Son exactamente dos modelos: **Q-learning** con tabla y **PPO** con red neuronal. Experto, prudente, maestro y
aleatoria son pilotos de referencia, no agentes.

## Qué hicimos

| Fecha | Hito |
|---|---|
| 23 oct | Miguel crea el repositorio |
| 28 oct | Ficha del ambiente, circuito de Mónaco y primer modelo (v1) |
| 29 oct | Sensor de agarre (v2), intento fallido con lluvia (v3) y DAgger, que resuelve la lluvia (v4) |
| 30 oct | Visor 3D estilo transmisión y DAgger para Q-learning (v6) |
| 1 nov | Ambiente 0.4, API, web en Vercel, manifiestos, Prefect, rollback, semillas y test reservado |

El detalle está en la [bitácora](registro/bitacora.md).

### Evolución de los modelos

| Versión | Hipótesis | Seco | Lluvia | Decisión |
|---|---|---|---|---|
| v1 | Primer modelo, entrenado en seco | 100 % | 0 % | Reemplazada |
| v2 | Un sensor de agarre ayuda con lluvia | 100 % | 0 % | Reemplazada |
| v3 | Practicar con lluvia e imitar vueltas | 0 % | 0 % | Rechazada |
| v4 | DAgger corrige los errores de la red | 100 % | 100 % | Reemplazada |
| **v5 semilla 1** | Conocer el carro y practicar todo con ruido | **100 %** | **100 %** | **Recomendada** |

Q-learning pasó de 0 % en sus primeras versiones a 60 % / 15 % (v6), 87 % / 81 % (v7) y 100 % / 100 % (v8 semilla 1).

### Tres aprendizajes

1. **Un 100 % puede engañar.** La v4 daba 100 % en la evaluación oficial y 0 % en 11 de 35 combinaciones de los
   deslizadores, porque solo se había medido con los parámetros base.
2. **El problema de la lluvia extrema era físico.** Con μ 0.4 el pedal gastaba todo el agarre y no quedaba para girar.
   Lo resolvió el control de tracción, no ir más lento.
3. **Una sola semilla engaña.** La semilla 0, promovida primero, resultó la más lenta y la menos robusta de PPO.

### Resultado final

Test reservado: 100 semillas fuera del repositorio, una sola corrida, con los modelos ya elegidos.

| Modelo | Seco | Lluvia | Extremos | Peores pruebas |
|---|---|---|---|---|
| **PPO v5 semilla 1** | **100 %, 68.6 s** | **100 %, 89.3 s** | **99.9 %** | Diluvio 98 % |
| Q-learning v8 semilla 1 | 99 %, 81.0 s | 99 %, 106.9 s | 84.8 % | Ruido en sensores 14 y 11 %, diluvio 60 % |

Las tablas completas están en la [ficha](ambiente-v0.1.md) y en el [informe](entregas/informe.md).

## Estado de los entregables

| Entregable | Estado | Dónde |
|---|---|---|
| Ficha del ambiente y 3 niveles | Falta nombre del equipo e intercambio | [ambiente-v0.1.md](ambiente-v0.1.md) |
| Código y pruebas | Listo, 54 pruebas pasando | `src/`, `tests/` |
| Modelos y datos versionados | Listos, en DVC con dos remotos | `dvc.lock`, `finalistas.dvc` |
| Manifiestos con SHA-256 | Listos, 16 versiones | [manifests/](../manifests/) |
| Experimentos | Listos en DagsHub | [MLflow](https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments) |
| Pipeline con Prefect | Probado sin entrenar | [pipelines/flujo.py](../pipelines/flujo.py) |
| Rollback | Probado v5 → v4 → v5 contra la API | [manifests/historial.json](../manifests/historial.json) |
| Evidencia del flujo | Lista | [evidencia/flujo/](evidencia/flujo/) |
| Monitoreo | Funciona con la API; en replay no hay datos | Catálogo de la web |
| Web en Vercel | Publicada en modo replay | https://autonomous-rally.vercel.app |
| API con FastAPI | Funciona en local, sin publicar | [src/rally/api.py](../src/rally/api.py) |
| Contenedor de la API | Sin construir: el equipo no ha tenido Docker | [deploy/api/](../deploy/api/) |
| Informe | Borrador completo | [entregas/informe.md](entregas/informe.md) |
| Presentación | Lista, sin ensayar | [entregas/presentacion/](entregas/presentacion/) |

## Lo que falta

| Tarea | Responsable | Prioridad |
|---|---|---|
| Preguntar al docente dónde publicar la API (propuesta: Hugging Face Space) | Kevin, miércoles | Alta |
| Publicar la API, conectar la web y probar la evaluación en vivo | Equipo | Alta |
| Probar el contenedor en un equipo con Docker | Equipo | Alta |
| Confirmar que Prefect es lo acordado (la otra opción era Airflow) | Equipo | Media |
| Nombre del equipo y contribuciones en ficha, informe y presentación | Equipo | Media |
| Intercambiar la ficha con otro equipo y corregir ambigüedades | Equipo | Media |
| Publicar el modelo final en Hugging Face; hoy tiene PPO v4 | Kevin | Media |
| Rotar los tokens de Hugging Face y DagsHub | Kevin | Media |
| Actualizar la web con la versión final de `main` | Kevin | Media |
| Ensayar la sustentación: cada integrante debe poder explicar ambiente, versionamiento y despliegue | Todos | Alta |

## Límites que hay que decir en la sustentación

- **Hay un solo circuito.** Medimos robustez ante condiciones, no manejo en una pista desconocida.
- **La web hoy no simula.** Muestra vueltas grabadas y lo dice en pantalla.
- **Q-learning falla con ruido en sensores:** sus celdas son más finas que el ruido.
- **La nota de velocidad segura es ayuda ya procesada.** No medimos cuánto depende el agente de ella.
- **Las hipótesis de v1 a v4 se escribieron después de entrenar,** y están marcadas así en MLflow.

## Cómo empezar a trabajar

La [guía para empezar](guias/empezar.md) explica cómo instalar, bajar los modelos, correr la web y colaborar.
El mapa de carpetas está en [docs/README.md](README.md).

Reglas del equipo:

- Trabajar en ramas y unir a `main` cuando las pruebas pasen.
- No subir tokens: van en `.env`, que está fuera de git.
- Si cambias `policies.py`, `pipeline.py` o `env.py`, `dvc repro` puede reentrenar PPO: revisa `dvc status` antes.
- **El test reservado ya se usó.** No lo repitas para ajustar modelos: pierde su valor.

## Enlaces

| Qué | Enlace |
|---|---|
| Repositorio | https://github.com/melo11miguel/defiende-el-servidor |
| Web | https://autonomous-rally.vercel.app |
| Experimentos | https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments |
| Datos y modelos | https://dagshub.com/kevin-nieto-callejas/autonomous-rally |
| Modelo publicado (PPO v4) | https://huggingface.co/Kevinnieto0001/autonomous-rally-ppo |
