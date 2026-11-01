# Ambiente v0.1 — Autonomous Rally · Circuito Mónaco

> Equipo: _______ · Versión del ambiente **0.4** (circuito Mónaco, 24 observaciones, configuración visible para el agente) · 1 nov 2026
> Mapa: [mapa-ambiente-v0.1.svg](mapa-ambiente-v0.1.svg), generado desde el código con `rally mapa --svg`.
> Ficha original del curso: [ficha-autonomous-rally.png](ficha-autonomous-rally.png)

**Historial de versiones** (cada una recuperable desde git):

| Versión | Cambios | Dónde |
|---|---|---|
| Pista rectangular | Pista de 239 m, 3 checkpoints | etiqueta `ambiente-v0.1` |
| 0.1-monaco | Circuito de Mónaco, muros, notas del copiloto (16 observaciones). Modelo entrenado: `modelo-v1` | etiqueta `modelo-v1` |
| 0.2 | Sensor de agarre (19 observaciones); correcciones de una revisión de código: estancarse cuesta −50, la puerta cruzada pisando el escape cuenta al volver, círculo de fricción con la velocidad nueva, contorno del carro cada 0.5 m. Modelo entrenado: `modelo-v2` | etiqueta `modelo-v2` |
| 0.3 | Sensor de lluvia (20 observaciones) y entrenamiento con lluvia en la mitad de los episodios (μ entre 0.45 y 0.6). Modelo: `modelo-v4` | etiqueta `modelo-v4` |
| **0.4** | Nueva familia de modelos (24 observaciones): el agente conoce ancho, aceleración y alcance, recibe una nota de frenada a 100 m y los rayos tienen escala fija. Los modelos anteriores corren con un adaptador validado | esta ficha |

## Niveles de dificultad

| Nivel | Qué decide el agente | Condiciones | Cómo se mide | Modelos |
|---|---|---|---|---|
| **N1 · Misión base** | Trazar y dosificar la velocidad para no salirse | Mónaco en seco, parámetros base | Vueltas y tiempo, 100 semillas | `modelo-v1`, `modelo-v2` |
| **N2 · Más decisiones** | Elegir cómo manejar según el clima, sin ver μ | Seco y lluvia (μ 0.45–0.6) | Mismo protocolo en los dos pisos | `experimento-v3`, `modelo-v4`, `modelo-qlearning-v6` |
| **N3 · Operación exigente** | Adaptarse a su carro y a perturbaciones | μ 0.4–1, ancho 6–12 m, a_max 2–6, sensores 10–40 m y ruido | Prueba de generalización por condición | Familia 0.4 |

Los gráficos no agregan dificultad: lo que cambia entre niveles son reglas, condiciones y lo que el
agente debe decidir. Los niveles anteriores siguen disponibles porque cada modelo conserva su ambiente
compatible, según su manifiesto en `manifests/`.

## Mision y mapa

**Misión:** dar una vuelta completa al circuito pasando los 6 checkpoints **en orden** y cruzar la meta,
sin chocar contra el muro ni salirse de la pista, en el menor tiempo posible.

![Mapa del circuito](mapa-ambiente-v0.1.svg)

**Geometría (vista superior, 2D, metros, origen en el centro del mapa, eje y hacia arriba):**

| Elemento | Definición |
|---|---|
| Trazado | 18 vértices con un radio de curva cada uno. Entre vértices hay rectas y en cada vértice un arco tangente a ambas rectas (así se diseñan los circuitos) |
| Largo de vuelta | **1 048.6 m** por la línea central, en sentido antihorario |
| Ancho de pista | w = 8 m |
| Zona de escape | 2 m a cada lado del borde, con adherencia baja |
| Muro (Armco) | A w/2 + 2 = 6 m del centro, a ambos lados. Tocarlo es choque |
| Mapa | 412.6 × 245.5 m (x en [−206.3, 206.3], y en [−122.8, 122.8]) |
| Salida / Meta | (42.8, −97.8), en la recta Anthony Noghes → Sainte Dévote, mirando al este (ψ = 0) |
| Carro | Largo 4.0 m, ancho 1.8 m, distancia entre ejes 2.5 m, modelo cinemático de bicicleta |

**Curvas** (velocidad máxima teórica: v = √(μ·g·r)):

| Curva | Radio | Giro | v máx. seco (μ = 0.9) | v máx. mojado (μ = 0.5) |
|---|---|---|---|---|
| Anthony Noghes | 16 m | +49° | 11.9 m/s | 8.9 m/s |
| Sainte Dévote | 13 m | +79° | 10.7 m/s | 8.0 m/s |
| Beau Rivage | 90 m | +31° | 28.2 m/s | 21.0 m/s |
| Massenet | 38 m | +76° | 18.3 m/s | 13.7 m/s |
| Casino | 28 m | −39° | 15.7 m/s | 11.7 m/s |
| Casino salida | 24 m | +37° | 14.6 m/s | 10.8 m/s |
| Mirabeau Haute | 13 m | +90° | 10.7 m/s | 8.0 m/s |
| **Fairmont (horquilla)** | **9.5 m** | **−93°** | **9.2 m/s** | **6.8 m/s** |
| **Fairmont salida** | **9.5 m** | **−90°** | **9.2 m/s** | **6.8 m/s** |
| Mirabeau Bas | 12 m | +87° | 10.3 m/s | 7.7 m/s |
| Portier | 14 m | +15° | 11.1 m/s | 8.3 m/s |
| Túnel | 120 m | +57° | 32.5 m/s | 24.3 m/s |
| Nouvelle Chicane | 11 m | +77° | 9.9 m/s | 7.3 m/s |
| Nouvelle Chicane salida | 11 m | −72° | 9.9 m/s | 7.3 m/s |
| Tabac | 15 m | +114° | 11.5 m/s | 8.6 m/s |
| Piscine | 13 m | −46° | 10.7 m/s | 8.0 m/s |
| Piscine salida | 13 m | +53° | 10.7 m/s | 8.0 m/s |
| Rascasse | 10 m | −65° | 9.4 m/s | 7.0 m/s |

La suma de los giros es exactamente 360°: el trazado da una sola vuelta y no se cruza. Las pruebas
automáticas lo verifican, junto con que dos tramos no vecinos nunca queden a menos de 18 m.

**Checkpoints** (puertas a 12 m de la salida de su curva):

| Puerta | Ubicación | s (m) |
|---|---|---|
| CP1 | Después de Beau Rivage | 251.9 |
| CP2 | Después de la salida del Casino | 413.7 |
| CP3 | Después de la horquilla de Fairmont | 556.0 |
| CP4 | Final del túnel | 768.1 |
| CP5 | Después de la Nouvelle Chicane | 811.2 |
| CP6 | Después de la Piscine | 913.8 |
| Meta | Línea de salida | 1 048.6 |

## Variables y unidades

### Parámetros del escenario

| Parámetro | Símbolo | Unidad | Base | Rango | Justificación | ¿Lo ve el agente? |
|---|---|---|---|---|---|---|
| Ancho de pista | w | m | 8 | [6, 12] | El carro mide 1.8 m. Mónaco es angosto: con 6 m quedan 2 m por lado | Sí (v0.4) |
| Adherencia del asfalto | μ | coeficiente | 0.9 | [0.4, 1.0] | 0.9 ≈ asfalto seco y 0.5 ≈ mojado | No |
| Adherencia del escape | μ_e | coeficiente | 0.35 | fija | Fuera del asfalto se agarra mucho menos | No |
| Aceleración máxima | a_max | m/s² | 4 | [2, 6] | 0→100 km/h en ~7 s | Sí (v0.4) |
| Frenado máximo | b_max | m/s² | 8 | fijo | Frenada fuerte en seco | No |
| Alcance de sensores | r_max | m | 20 | [10, 40] | Para frenar de 20 a 9 m/s antes de la horquilla hacen falta ~20 m | Sí (v0.4) |
| Velocidad máxima | v_max | m/s | 25 | fija | 90 km/h | No |
| Dirección máxima | δ_max | ° | 30 | fija | Ángulo típico de las ruedas delanteras | No |
| Paso de tiempo | dt | s | 0.1 | fijo | 10 Hz | No |
| Resistencia | k | 1/s | 0.05 | fija | El carro pierde velocidad si no acelera | No |

### Estado del mundo

| Variable | Significado | Unidad | Rango | ¿Lo ve el agente? |
|---|---|---|---|---|
| x, y | Posición del centro del carro | m | mapa | No |
| ψ | Orientación (0 = este, antihorario positivo) | rad | [−π, π) | No (solo el error respecto a la pista) |
| v | Velocidad hacia adelante | m/s | [0, 25] | Sí |
| ω | Velocidad de giro | rad/s | [−2, 2] | Sí |
| s | Progreso acumulado sobre la línea central (negativo si arranca detrás de la línea; pasa de 1 048.6 al cruzar la meta) | m | [−1, ~1 052] | No |
| s_best | Máximo progreso válido alcanzado | m | [0, 1 048.6] | No |
| d | Desvío lateral del centro (+ = izquierda) | m | [−6, 6] | Sí (normalizado) |
| next_cp | Siguiente puerta que hay que cruzar (8 = vuelta terminada) | entero | {1…8} | Indirectamente (dirección) |
| t | Tiempo del episodio | s | [0, 180] | No |
| t_fuera | Tiempo seguido fuera del asfalto | s | [0, 1.0] | No |
| uso de agarre | Aceleración de las llantas / (μ·g) | — | [0, 1] | Sí |
| derrape | Si las llantas están en su límite en este paso | bool | {0, 1} | Sí |
| μ estimado | Menor agarre medido en el episodio (empieza en 1.2 = sin medir) | — | [0, 1.2] | Sí |
| lluvia | Si el asfalto está mojado (μ < 0.75) | bool | {0, 1} | Sí |

## Observaciones y acciones

### Observación (vector de 24 valores normalizados)

| # | Componente | Cálculo | Rango |
|---|---|---|---|
| 0 | Velocidad | v / v_max | [0, 1] |
| 1 | Giro | clip(ω / 2, −1, 1) | [−1, 1] |
| 2–3 | Dirección al siguiente checkpoint | sin φ, cos φ (φ = ángulo entre el rumbo y la puerta) | [−1, 1] |
| 4 | Desvío del centro | clip(d / (w/2), −2, 2) | [−2, 2] |
| 5 | Error de rumbo respecto a la pista | e_ψ / π | [−1, 1] |
| 6–12 | 7 rayos a −90°, −60°, −30°, 0°, +30°, +60° y +90° | distancia al borde de pista o al muro / 40 m (hasta v0.3: / r_max) | [0, 1] |
| 13–15 | **Notas del copiloto** | curvatura de la pista a 10, 25 y 50 m adelante × 9.5 m (+ izquierda, − derecha) | [−1, 1] |
| 16 | **Uso de agarre** | aceleración de las llantas / (μ·g), recortado a 1 | [0, 1] |
| 17 | **Derrape** | 1 si las llantas están en su límite en este paso | {0, 1} |
| 18 | **Agarre estimado** | menor μ medido en el episodio / 1.2 | [0, 1] |
| 19 | **Lluvia** | 1 si el asfalto está mojado (μ < 0.75), como el sensor de lluvia del parabrisas | {0, 1} |
| 20 | **Ancho de pista** | w / 12 | [0, 1] |
| 21 | **Aceleración máxima** | a_max / 6 | [0, 1] |
| 22 | **Alcance de sensores** | r_max / 40 | [0, 1] |
| 23 | **Velocidad segura** | velocidad para llegar bien a lo que viene en 100 m, supone μ 0.8 en seco y 0.45 con lluvia / v_max | [0, 1] |

**Configuración visible (v0.4):** medir el PPO v4 en toda la zona de los deslizadores mostró que chocaba
al cambiar el alcance: como los rayos se dividían por r_max, la misma lectura significaba otra distancia.
Tampoco conocía su ancho ni su aceleración. Ahora los rayos tienen escala fija y el agente conoce su carro.
Son datos que cualquier piloto tiene. **μ sigue sin verse:** ese es el reto del incidente.

**Velocidad segura (v0.4):** la tabla de Q-learning veía 50 m, y frenar con lluvia desde 22 m/s pide
unos 72 m. Esta nota resume los siguientes 100 m en un número. Al comparar velocidad y nota, la tabla
sabe si le sobra velocidad, sin multiplicar sus estados.

**Notas del copiloto:** en el rally real el copiloto le lee al piloto las curvas que vienen ("derecha
cerrada en 50"). Sin ellas, con rayos de 20 m, el agente no puede saber a tiempo que viene la horquilla.

**Sensor de agarre (v0.2):** el modelo v1 chocaba con lluvia en Sainte Dévote porque no tenía forma de
saber que el piso estaba mojado. El agente sigue **sin ver μ directamente**, pero ahora tiene lo que mide
un control de tracción real. Cuando las llantas llegan a su límite (al frenar o al girar fuerte), el
simulador mide el agarre disponible y lo guarda como "agarre estimado". Por ejemplo, en mojado una
frenada fuerte satura las llantas (8 m/s² > 0.5·g) y revela μ ≈ 0.5; en seco no se satura (8 < 0.9·g)
y el estimado sigue en "sin medir". Así el agente puede aprender a "probar los frenos" en la recta.

**Sensor de lluvia (v0.3):** la v2 mostró que el sensor de agarre llega tarde: cuando las llantas se
saturan, el carro ya va demasiado rápido para Sainte Dévote. Un piloto real ve que llueve antes de
arrancar, así que el agente recibe una señal de lluvia (sí/no) desde el primer paso. Sigue sin ver el
valor exacto de μ: con lluvia el agarre puede estar entre 0.45 y 0.6 y tiene que manejar bien en todo
ese rango. Además, la mitad de los episodios de entrenamiento son con lluvia (`prob_lluvia: 0.5` en
`params.yaml`); en la v2 la lluvia era rara y el modelo casi no la practicaba.

### Acción (continua, 2 controles)

| Control | Rango | Significado |
|---|---|---|
| u_acel | [−1, 1] | Valores positivos aceleran (u·a_max); valores negativos frenan (u·b_max). No hay reversa: v ≥ 0 |
| u_dir | [−1, 1] | Ángulo de ruedas δ = u_dir · δ_max (+ = izquierda) |

Para Q-learning con tabla, las acciones se vuelven discretas: 6 de pedal × 9 de dirección = 54 acciones.
El estado se agrupa en 117 600 celdas (desvío, error de rumbo, velocidad, curvatura a 10 y 25 m, lluvia y
margen de frenada). **Pérdida de resolución:** la tabla no distingue situaciones dentro de una misma celda
ni acciones intermedias. Por eso maneja con menos precisión que la red, y esa diferencia se reporta. En la
tabla, el pedal significa m/s² y no un porcentaje: así sirve con cualquier a_max.

## Dinamica

En cada paso (dt = 0.1 s), el simulador aplica estas reglas en orden:

1. Recorta las acciones a [−1, 1] y calcula δ = u_dir · 30°.
2. Elige la adherencia: μ en el asfalto (|d| ≤ w/2) o μ_e = 0.35 en la zona de escape.
3. Calcula la fuerza de las llantas: `u_acel·a_max` o `u_acel·b_max`, recortada a μ·g. Luego resta la
   resistencia `k·v` (no es fuerza de las llantas, así que no gasta agarre) y obtiene la velocidad nueva v'.
4. Aplica el **círculo de fricción** con la velocidad nueva v' (la misma con la que se integra el giro):
   la aceleración de las llantas no puede pasar μ·g. Si la curva pide más aceleración lateral de la
   disponible, el carro **subvira** (gira menos de lo ordenado y se abre). Si las llantas llegan a su
   límite, se marca derrape y se actualiza el agarre estimado.
   **Consecuencia importante:** si el pedal pide todo el agarre, no queda nada para girar. Por eso los
   pilotos de μ baja necesitan control de tracción (ver "Metricas e incidente").
5. Integra la bicicleta cinemática: ψ, x, y.
6. Proyecta la posición sobre la línea central (KD-tree sobre muestras cada 0.25 m) para obtener s y d.
   Un salto de s mayor que lo que se puede recorrer en un paso se ignora: es una proyección sobre otro
   tramo cercano, como en la horquilla.
7. Aplica las reglas:
   - **Checkpoint:** cuenta cuando el carro está en el asfalto y ya pasó la puerta de `next_cp` hace
     menos de 30 m (lo que se recorre en el segundo máximo fuera de pista). Así, si cruzó la puerta
     pisando el escape, cuenta al volver al asfalto; pero aparecer mucho más adelante es un atajo y no cuenta.
   - **Progreso:** se paga el nuevo máximo de s, pero **nunca más de lo que el carro avanzó en ese paso**
     ni más allá de la próxima puerta sin cruzarla.
   - **Choque:** si algún punto del contorno del carro (muestreado cada ~0.5 m) pasa el muro
     (|d| > w/2 + 2 m).
   - **Fuera de pista:** si el centro del carro sale del asfalto, suma tiempo fuera.

## Recompensa

`r = r_prog + r_cp + r_vuelta + r_tiempo + r_fuera + r_suave + r_fin`

| Término | Valor | Cuándo |
|---|---|---|
| r_prog | +0.1 por metro de avance válido | En el asfalto, solo el avance real del paso |
| r_cp | +10 | Al cruzar el checkpoint que toca (CP1 a CP6), una vez |
| r_vuelta | +50 | Al cruzar la meta después de CP6 |
| r_tiempo | −0.05 por paso | Siempre |
| r_fuera | −1.0 por paso | Mientras el centro del carro está fuera del asfalto |
| r_suave | −0.2·\|Δu_dir\| − 0.05·\|Δu_acel\| | Penaliza los cambios bruscos de mando |
| r_fin | −50 | Al chocar, al salir del asfalto por ≥ 1 s o al quedar estancado 10 s |

**Escala:** una vuelta limpia en ~78 s da ≈ +105 (progreso) + 60 (CP) + 50 (vuelta) − 39 (tiempo) −
(suavidad) ≈ **+170**. El piloto experto obtiene +169.6 en seco.

## Exito, fracaso y limite de tiempo

| Resultado | Condición | Tipo de fin |
|---|---|---|
| **Éxito** | Cruzar CP1 a CP6 y la meta en orden, en el asfalto | `terminated` |
| **Choque** | El contorno del carro toca el muro | `terminated`, −50 |
| **Salida de pista** | 10 pasos seguidos (1 s) con el centro fuera del asfalto | `terminated`, −50 |
| **Estancado** | s_best no mejora en 10 s | `terminated`, −50 |
| **Límite de tiempo** | t = 180 s (1 800 pasos), unas 2.3 veces la vuelta experta | `truncated` |

**Estado inicial:** en la línea de salida, desvío lateral U(−0.5, 0.5) m, rumbo ±U(−5°, 5°), v = 0.

## Metricas e incidente

**Protocolo:** 100 episodios con semillas fijas (0–99), política en modo determinista. Las semillas de
entrenamiento son distintas (Q-learning desde 100 000, PPO desde 200 000, dataset desde 500), así el
modelo nunca se evalúa en los mismos arranques con los que entrenó.

**Resultados del modelo v1** (`modelo-v1`, 1 millón de pasos):

| Piloto | Seco: vueltas | Seco: tiempo | Mojado: vueltas | Mojado: avance |
|---|---|---|---|---|
| PPO (red neuronal) | 100 % | 77.6 s | 0 % | 57.6 % |
| Q-learning (tabla) | 0 % | — | 0 % | 11.9 % |

**Resultados del modelo v2** (`modelo-v2`, ambiente 0.2 con sensor de agarre, 3 millones de pasos):

| Piloto | Seco: vueltas | Seco: tiempo | Mojado: vueltas | Mojado: avance |
|---|---|---|---|---|
| PPO (red neuronal) | 100 % | **63.1 s** (−18.5 %) | 0 % | 11.6 % |
| Q-learning (tabla) | 0 % (21.7 % de avance) | — | 0 % | 11.7 % |

Lectura: en seco la v2 es mucho más rápida que la v1 y que el piloto experto. Con lluvia empeoró:
el modelo aprendió a ir más agresivo y el sensor de agarre no bastó para que frene antes. El
protocolo de la ficha no acepta la v2 (no mejora en mojado).

**Resultados del experimento v3** (`experimento-v3`, ambiente 0.3): rechazado, 0 % en seco y en lluvia.
Practicar con lluvia e imitar vueltas perfectas no bastó: al primer error la red llegaba a estados que
nunca había visto y chocaba en Sainte Dévote.

**Resultados del modelo v4** (`modelo-v4`, DAgger con piloto maestro + PPO 2 millones de pasos):

| Piloto | Seco: vueltas | Seco: tiempo | Mojado: vueltas | Mojado: tiempo |
|---|---|---|---|---|
| PPO v4 | 100 % | 75.6 s | 100 % | 91.8 s |
| Q-learning v6 (`modelo-qlearning-v6`) | 60 % | 80.15 s | 15 % | 102.2 s |

**Lo que la evaluación oficial no mostraba:** ese 100 % solo valía cerca de los parámetros base. Con
20 semillas por condición, el PPO v4 dio 0 % con ancho 12, 0 % con sensores de 10, 15 y 40 m, 0 % con
ancho 6 y lluvia, y 85 % con μ 0.75. Por eso la evaluación ahora incluye esos extremos y define el nivel N3.

**Hallazgo de física:** se creía que con μ 0.4 ningún piloto podía completar la vuelta. No era por la
velocidad: el pedal pedía todo el agarre y no quedaba para girar. Con control de tracción, el piloto de
reglas completa 6 de 6 vueltas incluso con μ 0.4. Es lo que ahora aprenden ambos agentes.

**Resultados de la familia 0.4** (`modelo-v5` y `modelo-qlearning-v7`, 100 semillas por condición):

| Piloto | Seco: vueltas | Seco: tiempo | Mojado: vueltas | Mojado: tiempo | Incidentes (seco / mojado) |
|---|---|---|---|---|---|
| PPO v5 | 100 % | 75.9 s | 100 % | 92.0 s | 0 / 0 |
| Q-learning v7 | 87 % | 81.3 s | 81 % | 107.7 s | 0.25 / 0.36 |
| Maestro (referencia) | 100 % | 80.8 s | 100 % | 103.8 s | 0 / 0 |
| Experto (base) | 100 % | 77.4 s | 0 % | — | 0 / 2.0 |

**Prueba de generalización** (% de vueltas, semillas 1000–1099, distintas a las de la ficha):

| Prueba | PPO v5 | Q-learning v7 | Maestro | Prudente | Experto |
|---|---|---|---|---|---|
| Llovizna μ 0.65 / casi seco μ 0.72 | 100 / 100 | 91 / 92 | 100 / 100 | 100 / 100 | 100 / 100 |
| Más agarre μ 1.1 | 100 | 90 | 100 | 100 | 100 |
| Salida torcida, seco / lluvia | 100 / 100 | 70 / 58 | 100 / 100 | 100 / 100 | 100 / 0 |
| Sensores con ruido 3 %, seco / lluvia | 100 / 100 | 0 / 0 | 100 / 100 | 100 / 100 | 100 / 0 |
| Diluvio μ 0.4 | **82** | 36 | 100 | 0 | 0 |
| Límite de lluvia μ 0.75 | 100 | 55 | 100 | 100 | 100 |
| Pista de 6 m, seco / lluvia | 100 / 100 | 69 / 34 | 100 / 100 | 100 / 100 | 100 / 0 |
| Pista de 12 m, seco / lluvia | 100 / 100 | 73 / 93 | 100 / 100 | 100 / 100 | 100 / 0 |
| Sensores de 10 m, seco / lluvia | 100 / 100 | 87 / 91 | 100 / 100 | 100 / 100 | 100 / 0 |
| Sensores de 40 m, seco / lluvia | 100 / 100 | 87 / 91 | 100 / 100 | 100 / 100 | 100 / 0 |
| Carro lento a_max 2 | 100 | 24 | 100 | 100 | 100 |
| Carro rápido con lluvia a_max 6 | 100 | 91 | 100 | 0 | 0 |

**Decisión:** PPO v5 cumple los criterios de `configs/seleccion.yaml`, fijados antes de ver estos resultados
(99.1 % promedio en las pruebas; la peor es el diluvio, 82 %), y pasa a ser el modelo recomendado. Frente a la
v4 cede 0.3 s en seco y 0.2 s en lluvia, a cambio de completar las condiciones donde la v4 fallaba. No se
marca sobreajuste: cae 18 puntos en el diluvio y se toleran 20. Q-learning v7 también cumple sus criterios,
más bajos, y queda marcado con sobreajuste: el ruido en los sensores lo lleva a 0 %, porque las celdas de la
tabla son más finas que el ruido. Es la pérdida de resolución de discretizar.

**Limitación:** hay un solo circuito. Los modelos no están probados en otra pista: lo que se mide es
robustez ante cambios de condiciones, no capacidad de manejar en un trazado desconocido.

| # | Métrica | Definición |
|---|---|---|
| 1 | **Tasa de vueltas completas** | % de episodios que terminan en éxito |
| 2 | **Tiempo de vuelta** | Mediana y p90 (s) de los episodios exitosos |
| 3 | **Incidentes por episodio** | Promedio de (salidas de pista + choques) |

**Incidente:** asfalto mojado, μ de 0.9 a **0.5**, sin cambiar nada más. El candidato se acepta si:
- en mojado completa más vueltas que el modelo base, y
- en seco no pierde más de 5 puntos porcentuales de vueltas ni sube más de 5 % su tiempo mediano.

Referencia con los pilotos de base (`rally evaluar`):

| Piloto | Seco | Mojado |
|---|---|---|
| Experto (asume μ = 0.9) | 100 % · 77.5 s | 0 % (choca) |
| Prudente (asume μ = 0.5) | 100 % · 96.7 s | 100 % · 96.8 s |

## Cinco transiciones

Calculadas por el ambiente y verificadas por `rally transiciones` y las pruebas automáticas.
Parámetros base: w = 8, μ = 0.9, a_max = 4, b_max = 8, dt = 0.1.

| | Escenario | Estado inicial | Acción | Resultado | Recompensa |
|---|---|---|---|---|---|
| T1 | Arranque en la salida | s = 0, v = 0 | (+1, 0) | v' = 0.40 m/s, avanza 0.04 m | **−0.096** |
| T2 | Cruce del CP1 | 1 m antes del CP1, v = 20 | (+0.3, 0) | Avanza 2.00 m, cruza CP1 → next_cp = 2 | **+10.150** |
| T3 | Horquilla de Fairmont rápido | Entrada de Fairmont, v = 15 | (0, −1) | Pide más agarre del que hay: **derrapa** (subviraje) | **−0.101** |
| T4 | Choque contra el muro | s = 100, d = +4.5, rumbo +25°, v = 12 | (+0.5, 0) | El contorno pasa el muro → **choque** | **−51.050** |
| T5 | Llegada a la meta | 1 m antes de la meta, next_cp = 7 | (+1, 0) | Cruza la meta → **éxito** | **+50.040** |

**T1 a mano:** a_long = 1·4 − 0.05·0 = 4 → v' = 0.4 m/s → avanza 0.04 m.
Recompensa = 0.1·0.04 (progreso) − 0.05 (tiempo) − 0.05·|1 − 0| (cambio de pedal) = **−0.096**.

**T2 a mano:** a_long = 0.3·4 − 0.05·20 = 0.2 → v' = 20.02 → avanza 2.002 m.
Recompensa = 0.1·2.002 + 10 (CP1) − 0.05 = **+10.150**.

## Posibles trampas y decisiones pendientes

| Trampa | Cómo la evitamos | Prueba automática |
|---|---|---|
| Pasar dos veces por el mismo checkpoint | Solo cuenta `next_cp`, que nunca retrocede | `test_checkpoint_no_paga_dos_veces` |
| Ir y volver para cobrar progreso | Se paga sobre el máximo alcanzado (s_best) | `test_ir_y_volver_no_acumula` |
| Atajo: llegar a una puerta posterior sin pasar las anteriores | Progreso topado en la próxima puerta y solo por el avance real del paso. **Esta trampa la encontraron las pruebas en esta versión** y se corrigió | `test_atajo_no_paga` |
| Saltar de un tramo a otro cercano (horquilla) | Los saltos de s imposibles en un paso no cuentan | `test_salto_de_proyeccion_no_es_avance` |
| Quedarse quieto para no arriesgar | Estancarse 10 s termina el episodio con −50, igual que chocar. **En v0.1 costaba solo −5 y el Q-learning v1 aprendió a detenerse antes de la parte difícil**; lo encontró una revisión de código | `test_estancarse_no_es_salida_barata` |
| Cruzar una puerta pisando el escape y perderla | Cuenta al volver al asfalto (si fue hace menos de 30 m) | `test_puerta_cruzada_en_el_escape_cuenta_al_volver` |
| Ir en reversa | No hay reversa (v ≥ 0) | `test_sin_reversa` |

### Decisiones pendientes

1. **"Fuera de pista": ¿centro del carro o carrocería completa?** Hoy se usa el centro.
2. **¿El agente debe ver el tiempo restante?** Sin él, el truncamiento no es markoviano.
3. **Pesos de r_suave:** son tentativos; si el agente se vuelve tímido hay que bajarlos.
4. **¿El sensor de agarre es "trampa"?** El agente no ve μ, pero sí una medición que en un carro real
   da el control de tracción.
5. **Más vueltas o pistas aleatorias** para evitar que el agente memorice el circuito: sigue pendiente y
   es el límite principal de los resultados.
6. **¿La velocidad segura es demasiada ayuda?** Es información del mapa, como las notas del copiloto, pero
   ya viene procesada. Hay que comparar qué tanto depende el agente de ella.

Decisión ya resuelta: el ruido en los sensores entró como perturbación del nivel N3 (v0.4).
