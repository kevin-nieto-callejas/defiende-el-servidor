# Experimento v6: ¿el agente aprendió a manejar o memorizó Mónaco?

Este documento se escribió **antes** de evaluar la v6 y su control. La regla de elección y el uso de la pista
reservada quedan fijos en este commit; los resultados se agregan después, sin cambiar lo que dice aquí.

## Por qué

Todos los modelos hasta la v5 se entrenaron y evaluaron en una sola pista. Una métrica de 100 % en Mónaco no dice
si el agente sabe manejar o si se aprendió la secuencia de curvas. Para saberlo agregamos pistas nuevas
(`src/rally/track.py`). Las diseñamos distintas a propósito y antes de usarlas comprobamos que el experto, el
prudente y el maestro completan 10 de 10 vueltas en cada una, en seco y con lluvia.

| Pista | Largo | Curvas | Radio mínimo | Sentido | Uso |
|---|---:|---:|---:|---|---|
| Mónaco | 1 049 m | 18 | 9.5 m | antihorario | entrenamiento |
| Bosque | 1 142 m | 9 | 14 m | horario | entrenamiento |
| Puerto | 1 130 m | 15 | 8.5 m | antihorario | entrenamiento |
| Sierra | 1 099 m | 11 | 11 m | antihorario | **prueba reservada** |
| Puerto r9.5 | 1 129 m | 15 | 9.5 m | antihorario | control del diagnóstico (solo evaluación) |

## Lo que ya medimos con la v5-s1

Con el protocolo de la ficha (100 semillas, seco μ = 0.9 y lluvia μ = 0.5), `ppo-modelo-v5-s1`, entrenado solo en
Mónaco, da 100 % en Mónaco y en el Bosque, pero **0 % en el Puerto**, en seco y con lluvia. El maestro completa el
Puerto el 100 % de las veces, así que la pista se puede manejar.

El Puerto tiene curvas de 8.5 m y 9 m, más cerradas que la más cerrada de Mónaco, y las notas de curvatura se
recortan en el radio de Mónaco: para el agente, una curva de 8.5 m se lee igual que una de 9.5 m. Para separar esa
causa de la memorización corrimos el Puerto con ninguna curva por debajo de 9.5 m: la v5-s1 sigue en 0 de 20 y se
estrella en los Contenedores, una curva que no es más cerrada que la horquilla de Mónaco. Concluimos que la v5-s1
sobreajustó a Mónaco.

## Diseño

Un solo cambio frente al control: las pistas de entrenamiento.

| | Control | v6 |
|---|---|---|
| Pistas de entrenamiento | Mónaco | Mónaco, Bosque y Puerto (una al azar por episodio) |
| Configuración de PPO y DAgger | `params.yaml` de la v5 | la misma |
| Semilla | 0 | 0 |
| Computador | el Mac de Miguel (Intel x86_64, PyTorch 2.2.2, numpy 1.26) | el mismo |

Entrenamos los dos en el mismo computador porque la v5 se entrenó en otro, con otras versiones de PyTorch y numpy:
comparar la v6 directamente con la v5 mezclaría dos cambios. La evaluación rápida que elige el mejor punto del
entrenamiento usa solo las pistas de entrenamiento de cada modelo.

**Hipótesis (en `params.yaml` antes de entrenar):** si la red practica en tres pistas en vez de solo Mónaco,
completa al menos 80 % de las vueltas en la Sierra, que nunca ve, sin perder más de 5 puntos ni más de 5 % de
tiempo en Mónaco frente al control.

## Fase A: validación (sin la Sierra)

`scripts/analisis/sobreajuste_pistas.py` con 100 semillas, seco y lluvia, en Mónaco, Bosque, Puerto y Puerto
r9.5, para el experto, el maestro, la v5, la v5-s1, el control y la v6. Esta fase se puede repetir.

## Regla de elección (fija desde este commit)

Elegimos la **v6** si cumple las dos condiciones; si no, elegimos el **control**:

1. En Mónaco no pierde frente al control: vueltas completas ≥ las del control menos 5 puntos, y tiempo mediano
   ≤ 1.05 veces el del control, en seco y con lluvia.
2. En el Puerto, que la v6 vio al entrenar, completa al menos 95 % de las vueltas en seco y con lluvia (muestra que
   aprendió las pistas de entrenamiento y no solo una).

La elección se escribe en este documento y se sube en un commit **antes** de la fase B.

## Fase B: prueba reservada (la Sierra, una sola vez)

Después del commit de la elección corremos una sola vez:

```bash
python scripts/analisis/sobreajuste_pistas.py --reservada \
  --modelo ppo-modelo-v5-s1=<npz>:monaco --modelo control=<zip>:monaco \
  --modelo v6=<zip>:monaco,bosque,puerto --salida metrics/sierra-v6.json
```

Van los tres modelos congelados porque la hipótesis compara la v6 con el control precisamente en la Sierra. El
script se niega a correr si `metrics/sierra-v6.json` ya existe. El resultado se guarda tal cual, aunque contradiga
la hipótesis, y **no cambia la elección** ni lleva a reentrenar o ajustar nada.

## Entrenamiento

| | Control | v6 |
|---|---|---|
| DAgger | 20 iteraciones, 100 % en la evaluación rápida desde la 2 | igual |
| PPO | 3 000 000 de pasos, 3 879 episodios | 3 000 000 de pasos, 3 697 episodios |
| Mejor punto (evaluación rápida en sus pistas de entrenamiento) | paso 400 008 | paso 3 000 000 |
| SHA-256 del modelo | `8b469b4ffe8c…` | `528ea053635d…` |
| Run de MLflow | `af40fef528594dafb7675aab0f0c1900` | `a09ed36cd1bb46229665c93f659c87ea` |

El Mac se apagó por batería en el paso 400 008 de la v6. El entrenamiento continuó desde el punto de guardado de
ese paso (MLflow lo registra con la etiqueta `reanudado_desde_paso`); el run interrumpido quedó como `KILLED`
con una nota.

Los dos modelos se exportaron a numpy (`agentes/red_numpy.py`) y se compararon con PyTorch en 6 846 observaciones:
diferencia máxima de 7.2e-07 en la v6 y 5.4e-07 en el control. Todas las evaluaciones usan esa exportación,
igual que la API publicada.

## Fase A: resultados (`metrics/sobreajuste-pistas.json`)

Vueltas completas en 100 semillas, seco / lluvia, y tiempo mediano en segundos.

| Piloto | Mónaco | Bosque | Puerto | Puerto r9.5 |
|---|---|---|---|---|
| Experto (asume piso seco) | 100 / 0 · 77.4 s | 100 / 0 · 66.9 s | 100 / 0 · 89.2 s | 100 / 0 · 88.8 s |
| Maestro | 100 / 100 · 80.8 / 103.8 s | 100 / 100 · 69.2 / 86.3 s | 100 / 100 · 92.9 / 119.3 s | 100 / 100 · 92.4 / 118.9 s |
| v5, semilla 0 (Kevin) | 100 / 100 · 75.9 / 92.0 s | **0 / 0** | **0 / 0** | **0 / 0** |
| v5, semilla 1 (Kevin) | 100 / 100 · 68.6 / 89.3 s | 100 / 100 · 62.5 / 79.9 s | **0 / 0** | **0 / 0** |
| Control, solo Mónaco | 100 / 100 · 79.6 / 100.2 s | 100 / **30** · 68.8 / 87.7 s | 100 / 100 · 88.4 / 114.8 s | 100 / 100 · 88.4 / 114.4 s |
| **v6, tres pistas** | 100 / 100 · 69.8 / 86.6 s | 100 / 100 · 65.4 / 77.6 s | 100 / 100 · 78.8 / 99.5 s | 100 / 100 · 78.9 / 99.4 s |

Que el experto dé 0 % con lluvia es lo esperado: maneja como si el piso estuviera seco. El control choca con
lluvia en el Bosque en 70 de 100 vueltas, todas en el último tramo antes de la meta (la Horquilla del Lago).

## Elección (antes de la Sierra)

| Condición | Seco | Lluvia | ¿Cumple? |
|---|---|---|---|
| 1. Mónaco: vueltas ≥ control − 5 | 100 ≥ 95 | 100 ≥ 95 | sí |
| 1. Mónaco: tiempo ≤ 1.05 × control | 69.8 ≤ 83.6 s | 86.6 ≤ 105.2 s | sí |
| 2. Puerto ≥ 95 % | 100 | 100 | sí |

**Elegimos la v6.** Esta elección queda fija: el resultado de la Sierra no la cambia.

### Lo que la fase A ya enseña, y que matiza la hipótesis

- **Entrenar en una sola pista no basta para explicar el sobreajuste.** El control, entrenado solo en Mónaco,
  completa el Puerto el 100 % de las veces; la v5 y la v5-s1 dan 0 %. Una diferencia visible es cuánto
  afinó con PPO: el mejor punto del control fue el paso 400 008, casi la red recién imitada del maestro, y es
  más lento que las v5 en Mónaco (79.6 s contra 68.6 a 75.9 s), mientras que la v6 sí siguió mejorando su
  tiempo hasta el paso 3 000 000. Nuestra hipótesis es que afinar mucho en una sola pista lleva a memorizarla
  y afinar en tres no; no lo comprobamos, porque en el repositorio no está registrado el mejor paso de las v5.
- **La semilla importa.** La v5 y la v5-s1 tienen la misma configuración: una completa el Bosque y la otra
  no. Con una sola semilla por modelo, nuestras conclusiones sobre el control y la v6 tienen el mismo límite.
- El control y la v6 no son del mismo computador que las v5 (ver Diseño), así que comparamos la v6 con el
  control y usamos las v5 solo como referencia.

## Fase B: Sierra

Pendiente: se corre una sola vez después del commit de esta elección.
