# Flujo completo de Prefect con entrenamiento real

Corrida del 1 y 2 de noviembre de 2026, desde el commit `75ece1a`, en una copia aparte del repositorio para no
tocar los modelos oficiales. Usó 4 núcleos con prioridad baja.

| Etapa | Resultado |
|---|---|
| 1. Validar | Ambiente 0.4, observación de 24 valores |
| 2. Pruebas | 54 pasaron |
| 3. Entrenar y evaluar | `dvc repro` completo: datos, Q-learning, PPO, evaluación, registro y extremos |
| 4. Registrar | Manifiestos regenerados |
| 5. Seleccionar | `ppo-modelo-v5` cumple todos los criterios de `configs/seleccion.yaml` |
| 6. Promover | Promovido en la copia |
| 7. Publicar | Catálogo actualizado |
| 8. Comprobar | La API de la copia sirve `ppo-modelo-v5` |

## Reproducibilidad

El reentrenamiento dio **exactamente** los mismos resultados oficiales: 0 diferencias en vueltas y tiempos de los 5
pilotos, en las 2 condiciones de la evaluación y en las 21 de la prueba de extremos. Mismo código, mismos
parámetros y misma semilla producen el mismo modelo.

Los archivos de los modelos no son idénticos byte a byte, porque `info.json` guarda el id del run y la duración.

## Interrupción

El computador se suspendió de 1:12 a 8:06 a. m. por batería baja, con PPO en 1 millón de pasos. Al reanudar,
el entrenamiento siguió solo desde su punto de guardado, sin perder avance, y el resultado final no cambió.
