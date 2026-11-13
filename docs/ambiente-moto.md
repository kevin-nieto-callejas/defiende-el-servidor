# Ambiente moto-0.1 — Autonomous Rally MotoGP

La misma misión del carro con otro vehículo: una vuelta a Mónaco (o a Bosque y Puerto) pasando los
checkpoints en orden. Cambia la física, y con ella la decisión que el agente tiene que aprender.
Código: [`src/rally/moto.py`](../src/rally/moto.py). Gymnasium: `AutonomousRallyMoto-v0`.

El carro no cambió: su ambiente, sus modelos, sus rutas (`models/`, `metrics/`) y sus resultados son
los de siempre. La moto vive en `models/moto/`, `metrics/moto/`, `data/processed/moto/` y en la
sección `moto:` de `params.yaml`, con su propio experimento de MLflow (`autonomous-rally-motogp`).

## Qué decisión nueva toma el agente

| | Carro | Moto |
|---|---|---|
| Mando de dirección | ángulo de volante δ | inclinación pedida φ |
| Cómo gira | κ = tan δ / L | κ = g · tan φ / v² |
| Respuesta del mando | inmediata | la inclinación cambia a lo sumo 80 °/s (8° por paso) |
| Pasarse del agarre lateral | subvira: gira menos y sigue | patina; 3 pasos seguidos patinando (0.3 s) = **caída** |
| Frenar en curva | pierde giro | también patina: el círculo de fricción es el mismo, pero aquí tira la moto |
| Parada | puede girar el volante | no se puede inclinar (equilibrio) |

La moto obliga a **anticipar**: tiene que empezar a tumbarse antes de la curva, porque llegar a 35°
tarda casi medio segundo, y tiene que repartir el agarre entre frenar e inclinarse, porque gastarlo
todo en el freno con la moto inclinada la tira.

## Variables y unidades

| Parámetro | Carro | Moto | Unidad |
|---|---|---|---|
| `a_max` (aceleración máxima) | 4.0 | 5.0 | m/s² |
| `b_max` (frenada máxima) | 8.0 | 9.0 | m/s² |
| `v_max` | 25 | 32 | m/s |
| `drag` | 0.05 | 0.04 | 1/s |
| Largo × ancho | 4.0 × 1.8 | 2.1 × 0.8 (con piloto) | m |
| Entre ejes `L` | 2.5 | 1.45 | m |
| `phi_max_deg` (inclinación máxima pedible) | — | 60 | ° |
| `roll_rate_deg` (tasa de inclinación) | — | 80 | °/s |
| `slide_limit` (pasos patinando antes de caer) | — | 3 | pasos de 0.1 s |
| `delta_max_deg` (tope del manubrio) | 30 | 30, solo limita el equilibrio a baja velocidad | ° |

Pista, ancho, adherencia, escape, sensores, puertas, `dt` = 0.1 s, `max_steps` = 1800 y recompensa
son los del carro ([ficha del carro](ambiente-v0.1.md)). Los deslizadores del visor tienen los mismos
rangos; el valor base de la aceleración es el de cada vehículo.

## Observación y acción

Observación de **26** valores: las 24 del carro, en el mismo orden y con los mismos divisores
(salvo la velocidad y la velocidad segura, que se dividen por los 32 m/s de la moto), más:

| Índice | Valor | Rango |
|---|---|---|
| 24 | inclinación actual / 60° (positiva = a la izquierda) | [-1, 1] |
| 25 | riesgo de caída: pasos seguidos patinando / 3 | [0, 1] |

Acción `[u_acel, u_incl]` en [-1, 1]: pedal (como el carro) e inclinación pedida / 60°.

Como cambian las dimensiones y el significado de la acción, los modelos de la moto son **otra familia**:
un modelo del carro no corre en la moto ni al revés (la API responde 409 si se le pide).

## Dinámica de un paso

1. φ ← φ + clip(u_incl · 60° − φ, ±8°).
2. Pedal: a = u_acel · (a_max o b_max), recortado al agarre μ·g (como el carro).
3. v ← clip(v + (a − drag · v) · dt, 0, v_max).
4. Equilibrio: |φ| ≤ atan(v² · tan δ_max / (L · g)).
5. a_lat = g · tan|φ|; si a_lat > √((μg)² − a²) la moto patina: el giro se recorta a ese máximo y
   cuenta un paso patinando. 3 seguidos → `caida`.
6. Giro κ = a_lat / v² con el signo de φ; integración igual a la del carro.

## Éxito, fracaso y límite de tiempo

Los del carro (`exito`, `choque`, `salida`, `estancado`, `tiempo`) más **`caida`**, que cuesta lo mismo
que un choque (−50) y termina el episodio. En las métricas cuenta como incidente.

## Transiciones de la ficha

`rally transiciones --vehiculo moto` y `tests/test_moto.py` las comprueban.

| Id | Situación | Recompensa | Fin | Inclinación |
|---|---|---|---|---|
| M1 | Arranque a fondo en la salida (a mano: −0.05 − 0.05 + 0.1·0.05) | −0.095 | — | 0° |
| M2 | A 15 m/s pide 60°: solo llega a 8° | −0.101 | — | 8° |
| M3 | 40° con lluvia, tercer paso patinando | −49.901 | caída | 40° |
| M4 | Parada, pide inclinarse | −0.25 | — | 0° |

## Pilotos de referencia

Los mismos cuatro del carro, adaptados: el pure pursuit convierte la curvatura deseada en inclinación
(tan φ = v²κ/g), mira más adelante para compensar la tasa de inclinación, nunca pide más inclinación
de la que cree que aguanta el piso y trae control de tracción y ABS que reparten el agarre con la
inclinación. Suite de la ficha: 100 semillas, Mónaco, condición base de la moto.

| Piloto | Seco | Tiempo | Lluvia | Tiempo |
|---|---|---|---|---|
| experto (supone μ 0.9) | 100 % | 74.7 s | 0 % (se cae) | — |
| prudente (supone μ 0.5) | 100 % | 97.7 s | 100 % | 97.7 s |
| maestro (mira la lluvia: μ 0.8 / 0.42) | 100 % | 78.4 s | 100 % | 108.4 s |

El escenario del carro se repite: quien supone piso seco se cae con lluvia. El maestro de la moto
supone μ = 0.42 con lluvia (el del carro, 0.45) para completar toda la zona de los deslizadores,
incluso μ = 0.4: en la moto pasarse no subvira, tira la moto.

## Niveles

| Nivel | Moto | Evidencia |
|---|---|---|
| N1 · misión base | seco, μ 0.9, condición base | experto 100 %, suite de la ficha |
| N2 · más decisiones | lluvia: anticipar la frenada y no inclinarse de más | evaluación seco/lluvia de cada agente |
| N3 · operación exigente | generalización: 19 perturbaciones (agarre, ancho, sensores, ruido, salidas torcidas) | `metrics/moto/generalizacion.json` |

## Simplificaciones

- Modelo cinemático de una sola huella: no hay transferencia de carga, ni caballito, ni derrape
  controlado; el contragiro está implícito en la tasa de inclinación.
- La caída es instantánea tras 0.3 s patinando: no se modela recuperar la moto patinando.
- El piloto del visor se cuelga hacia el interior de la curva solo como dibujo: no cambia la física.

## Resultados de los agentes (versión `moto-v1`)

Entrenados con `dvc repro` (etapas `moto-*`) en un equipo de 2 CPU, con presupuesto reducido frente al
carro: PPO 20 iteraciones de DAgger + 1 millón de pasos (57 min); Q-learning 30 iteraciones de DAgger
+ 400 episodios (15 min). Experimentos en MLflow: `autonomous-rally-motogp`. Suite de la ficha: 100
semillas por condición (`metrics/moto/evaluacion.json`).

| Versión | Seco | Tiempo seco | Lluvia | Tiempo lluvia | Extremos (19 pruebas) | Decisión |
|---|---|---|---|---|---|---|
| `ppo-moto-v1` | 100 % | 78.2 s | 100 % | 110.0 s | 98.1 % (peor: `limite_lluvia` 63.3 %) | **aceptado y recomendado** |
| `qlearning-moto-v1` | 0 % | — | 96 % | 112.4 s | 40.4 % | rechazado |

Los criterios se fijaron antes de entrenar (`configs/seleccion.yaml`, sección `moto`); los veredictos
completos están en `manifests/moto/decisiones.json`.

**PPO: el refuerzo ganó velocidad y perdió confiabilidad.** El mejor punto fue el de la red recién
imitada (paso 0): 100 % en seco, lluvia y extremos en la evaluación rápida. Durante el refuerzo el
tiempo en seco bajó de 77.6 s a 72.6 s, pero los extremos cayeron a 61–89 % y la lluvia llegó a 47 %
en el paso 800 000. La regla de `MejorModelo` (vueltas primero, luego tiempo) se quedó con la red
imitada. Siguiente hipótesis: refuerzo con una tasa de aprendizaje menor o con el coeficiente de
recorte reducido, para conservar la robustez mientras baja el tiempo.

**PPO en `limite_lluvia` (μ = 0.75): 63 %.** Con ese agarre el sensor de lluvia marca seco (llueve por
debajo de 0.75), así que la moto entra a las curvas como en seco y se cae en 37 de cada 100 vueltas.
Es la misma frontera que el carro ya mostraba; en la moto pesa más porque pasarse tira la moto. La
regla de generalización la marca como sobreajuste (caída de 36.7 puntos > 20); los criterios de
selección la aceptan (peor prueba ≥ 50 %).

**Q-learning: la tabla no aprendió la moto en seco.** Con lluvia imita bien al maestro (96 %), pero en
seco se cae siempre. Ni el refuerzo mejoró la mejor tabla de la imitación. La tabla usa la
discretización del carro y no ve la inclinación: en seco va más rápido, necesita más inclinación y
llegar a ella a tiempo, y sin verla no sabe cuándo empezar a tumbarse. Siguiente hipótesis
(`qlearning-moto-v2`): agregar la inclinación (observación 24) a `discreto.py` con 3 rangos, que
triplica la tabla a 352 800 estados.

**Experto con lluvia.** Se cae en los primeros pasos: su control de tracción supone piso seco y deja
pasar 5 m/s² sobre un piso que aguanta 4.9; con la rueda patinando, cualquier inclinación lo tira.
Es el incidente esperado (quien supone seco no maneja con lluvia), igual que en el carro.
