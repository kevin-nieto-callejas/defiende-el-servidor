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

## Resultados

Pendiente: se agregan al terminar el entrenamiento.
