# Flujo de Prefect con un candidato rechazado (v6)

Corrida del 10 de noviembre de 2026, sin entrenar, con la v6 como candidata:

```bash
~/.venvs/rally-flujo/bin/python pipelines/flujo.py --candidato ppo-modelo-v6-pistas --tipo ppo --sin-entrenar
```

Los resultados de la v6 ya estaban en `metrics/` (`dvc repro -s evaluar` y `-s generalizacion`). Las 8 etapas
terminaron bien; el entrenamiento no corrió por `--sin-entrenar`.

| Etapa | Resultado | Archivo |
|---|---|---|
| 1. Validar | Ambiente 0.4, 24 observaciones | [validar.json](validar.json) |
| 2. Pruebas | 87 pasan | [pruebas.json](pruebas.json) |
| 4. Registrar | Manifiestos regenerados | [registrar.json](registrar.json) |
| 5. Seleccionar | **Rechazada**: extremos 79.2 % (mínimo 85) y diluvio 0 % (mínimo 50) | [seleccionar.json](seleccionar.json) |
| 6. Promover | No promueve | [promover.json](promover.json) |
| 7. Publicar | Paquete de la API al día | [publicar.json](publicar.json) |
| 8. Comprobar | La API sigue sirviendo `ppo-modelo-v5-s1` | [comprobar.json](comprobar.json) |

El veredicto también queda en [manifests/decisiones.json](../../../manifests/decisiones.json), el registro de todas
las decisiones de selección, aceptadas o no. Va aparte de `historial.json` porque el rollback vuelve a la entrada
anterior del historial, que solo tiene promociones.

**Antes de esta corrida hubo un intento que el propio flujo detuvo** en la etapa 2: se había cambiado el código y el
paquete de la API de Vercel ya no coincidía, así que una prueba falló. Se rearmó el paquete y se volvió a correr.
