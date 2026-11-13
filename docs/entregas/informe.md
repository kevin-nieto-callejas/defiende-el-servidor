# Informe: Autonomous Rally

Proyecto final de MLOps · Universidad Externado de Colombia · Docente: Julián Zuluaga
Equipo: _______ · Integrantes: Kevin Nieto, Miguel Melo y Allison Loango · Versión de borrador: 13 nov 2026

## Resumen

Entrenamos un agente que completa un circuito de 1 048.6 m inspirado en Mónaco, pasando seis checkpoints en
orden. El modelo recomendado hoy es **PPO v6 semilla 1**, entrenado en tres pistas. En su test reservado, corrido una
sola vez con semillas nuevas fuera del repositorio, completó el 100 % de las vueltas en seco (80.4 s) y con lluvia,
y el 100 % en las 19 condiciones más difíciles. Antes era la v5 semilla 1, que en su propio test reservado dio
100 % y 99.9 %. Cada versión se puede identificar por su manifiesto, recuperar y evaluar con su ambiente
compatible. Conservamos también los intentos fallidos.

El resultado más útil no fue un número sino una corrección: la v4 ya daba 100 % en la evaluación oficial y aun
así chocaba en los experimentos del visor. La evaluación solo cubría los parámetros base.

Después probamos si el agente sabe manejar o memorizó Mónaco, con tres pistas nuevas y una reservada. El modelo
recomendado de entonces (v5 semilla 1) da 0 % en dos pistas que el piloto maestro sí completa: memorizó el
circuito. La v6, entrenada en tres pistas, completa el 100 % en la pista reservada, pero su semilla 0 no pasó los
criterios de selección porque perdía aguante en condiciones extremas. Su semilla 1 sí los pasó (7 de 7) y pasó su
test reservado, así que se promovió el 12 de noviembre. Gana robustez y pistas nuevas a cambio de velocidad: es
11.8 s más lenta en seco que la v5 semilla 1.

Además, el ambiente tiene un segundo vehículo, una moto MotoGP con su propia física (gira inclinándose y puede
caerse), con los mismos dos agentes, su propia selección y su propio recomendado.

## Decisiones técnicas

| Decisión | Razón |
|---|---|
| Python es la autoridad del mundo; la web solo dibuja | Entrenamiento, evaluación y demostración usan las mismas reglas |
| Observaciones numéricas, no píxeles | Basta para la misión y entrena en CPU |
| El agente no ve la adherencia exacta, solo si llueve | Es el reto del incidente |
| Imitación con DAgger antes de PPO | Copiar vueltas perfectas falló: al primer error la red llegaba a estados nunca vistos (v3) |
| Nueva familia de modelos en v0.4 | Cambiaron las observaciones; las familias viejas corren con adaptador |
| Criterios de selección escritos antes de ver resultados | Evita ajustar la regla para que un modelo pase |

## Evolución de los experimentos

| Versión | Hipótesis | Seco | Lluvia | Decisión |
|---|---|---|---|---|
| `modelo-v1` | Primer modelo en seco | 100 % | 0 % | Reemplazado |
| `modelo-v2` | Un sensor de agarre ayuda con lluvia | 100 % | 0 % | Reemplazado: no ayudó |
| `experimento-v3` | Practicar con lluvia e imitar vueltas | 0 % | 0 % | Rechazado |
| `modelo-v4` | DAgger corrige los errores | 100 % | 100 % | Aceptado; luego reemplazado |
| `ppo-modelo-v5-s1` | Conocer el carro y practicar todos los deslizadores con ruido | 100 % | 100 % | Aceptado; reemplazado el 12 nov (queda para rollback) |
| `ppo-modelo-v6-pistas` | Practicar en tres pistas permite manejar en una que nunca vio | 100 % | 100 % | Hipótesis cumplida; rechazado por la selección |
| **`ppo-modelo-v6-pistas-s1`** | La misma v6 con otra semilla | **100 %** | **100 %** | **Recomendado** |

Q-learning con tabla: de 0 % en las primeras versiones a 60 % / 15 % (v6), 87 % / 81 % (v7) y 100 % / 100 % (v8,
semilla 1). En la v8 los episodios de Q-learning sí mejoraron la tabla de imitación; antes no aportaban.

**Contraste de finalistas.** Tres entrenamientos independientes por agente, con la misma suite:

| Modelo | Semilla | Seco | Lluvia | Extremos |
|---|---|---|---|---|
| PPO v5 | 0 | 100 %, 75.9 s | 100 %, 92.0 s | 98.5 % |
| **PPO v5** | **1** | **100 %, 68.6 s** | **100 %, 89.3 s** | **100 %** |
| PPO v5 | 2 | 100 %, 69.9 s | 100 %, 85.1 s | 99.8 % |
| Q-learning v8 | 0 | 99 %, 81.1 s | 100 %, 107.6 s | 85.0 % |
| **Q-learning v8** | **1** | **100 %, 81.0 s** | **100 %, 106.9 s** | **85.9 %** |
| Q-learning v8 | 2 | 95 %, 80.7 s | 98 %, 107.4 s | 81.9 % |

La media de PPO es 100 % ± 0 en seco y lluvia. La de Q-learning es 98.0 % ± 2.2 en seco y 99.3 % ± 0.9 con lluvia.
Una sola semilla habría engañado: la semilla 0, elegida primero, resultó la más lenta y la menos robusta de PPO.

**Test reservado** (100 semillas fuera del repositorio, una sola corrida, con los modelos ya elegidos):

| Modelo | Seco | Lluvia | Extremos | Peores pruebas |
|---|---|---|---|---|
| PPO v5 semilla 1 | 100 %, 68.6 s | 100 %, 89.3 s | 99.9 % | Diluvio 98 % |
| Q-learning v8 semilla 1 | 99 %, 81.0 s | 99 %, 106.9 s | 84.8 % | Ruido 14 y 11 %, diluvio 60 % |
| **PPO v6 semilla 1** (otra semilla secreta, 12 nov) | **100 %, 80.4 s** | **100 %, 104.8 s** | **100 %** | Ninguna bajo 100 % |

Casi igual a lo medido al seleccionar, así que no hay señales de que elegir la semilla haya inflado los números.
La v6 semilla 1 tuvo su propio test reservado: una semilla nueva, porque la anterior ya se había usado, con la regla
fijada en git antes de correrlo (commit `5ed48de`).

Las hipótesis de v1 a v4 y de Q-learning v6 se escribieron después de entrenar y están marcadas así en MLflow.
Las de la familia 0.4 se registraron antes.

## Incidente, degradación e intervención

**Incidente:** menor adherencia, μ de 0.9 a 0.5.

1. **Degradación:** el experto pasa de 100 % a 0 %. Los modelos v1 y v2 también.
2. **Primera intervención (v4):** resuelve la condición oficial.
3. **Segunda degradación, encontrada por nosotros:** con 20 semillas en 35 combinaciones de los deslizadores, la v4
   dio 0 % en 11 y 85 % en una. Los rayos se dividían por el alcance, así que mover ese deslizador cambiaba el significado de cada lectura.
4. **Hallazgo de física:** con μ 0.4 ningún piloto completaba la vuelta. No era velocidad: el pedal pedía todo el
   agarre y no quedaba para girar. El control de tracción lo resolvió.
5. **Segunda intervención (v5):** configuración visible, rayos en escala fija y práctica en todo el rango.

| Condición (100 vueltas) | PPO v4 | PPO v5 semilla 1 | Q-learning v8 semilla 1 |
|---|---|---|---|
| Seco | 100 %, 75.6 s | 100 %, 68.6 s | 100 %, 81.0 s |
| Lluvia | 100 %, 91.8 s | 100 %, 89.3 s | 100 %, 106.9 s |
| Sensores con ruido y lluvia | 63 % | 100 % | 9 % |
| Diluvio μ 0.4 | 0 % | 100 % | 52 % |

La columna de la v4 usa las semillas 1000–1099 en las dos últimas filas; las otras columnas, las semillas 0–99.

**Resultado de la intervención:** la semilla ganadora mejoró a la v4 sin costo. La semilla 0 sí cedía 0.3 s en seco
y 0.2 s con lluvia frente a la v4, así que no se debe atribuir toda la ganancia de tiempo al método.

## Experimento v6: ¿maneja o memorizó Mónaco?

Hasta la v5 todo se entrenó y evaluó en una sola pista, así que un 100 % no distinguía entre saber manejar y
haber memorizado las curvas. Agregamos tres pistas, distintas a propósito: Bosque (rápida, sentido horario),
Puerto (técnica, curvas de 8.5 m) y Sierra, reservada para la prueba (el código no deja entrenar con ella). El
experto, el prudente y el maestro completan las cuatro en seco y con lluvia.

**Diseño.** Un solo cambio frente a un control: la v6 practica en Mónaco, Bosque y Puerto; el control, solo en
Mónaco. Misma configuración, misma semilla y mismo computador. La hipótesis, la regla de elección y el uso único
de la Sierra se escribieron antes de ver resultados.

**Hipótesis:** si la red practica en tres pistas, completa al menos 80 % de las vueltas en la Sierra sin perder
más de 5 puntos ni 5 % de tiempo en Mónaco frente al control.

| Piloto (100 semillas, seco / lluvia) | Bosque | Puerto | Sierra (una sola corrida) |
|---|---|---|---|
| Maestro | 100 / 100 % | 100 / 100 % | 100 / 100 % |
| PPO v5 semilla 1 (recomendado entonces) | 100 / 100 % | **0 / 0 %** | **0 / 0 %** |
| Control, solo Mónaco | 100 / 30 % | 100 / 100 % | 100 / 100 %, 77.3 / 99.4 s |
| **v6, tres pistas** | 100 / 100 % | 100 / 100 % | **100 / 100 %, 68.8 / 88.0 s** |

La hipótesis se cumple. La lectura es más fina que "más pistas generaliza": el control también completa la
Sierra, aunque más lento. Lo que aportan las tres pistas es poder afinar con PPO sin memorizar; la v5 semilla 1,
afinada solo en Mónaco, sí memorizó.

**Selección.** Registrar un candidato no lo promueve. Corrimos la evaluación oficial y las pruebas extremas con la
v6 y aplicamos los criterios fijados el 1 de noviembre:

| Criterio | Mínimo | v6 | ¿Cumple? |
|---|---|---|---|
| Vueltas en seco / lluvia | 98 % | 100 % / 100 % | sí |
| Tiempo en seco | ≤ 81.3 s | 69.8 s | sí |
| Promedio en pruebas extremas | 85 % | **79.2 %** | **no** |
| Peor prueba | 50 % | **0 %**, diluvio | **no** |

Donde la v5 semilla 0 daba 82 a 100 %, la v6 da 0 % en diluvio, 14 % en el límite de lluvia, 5 % en la pista de
6 m en seco y 0 % con sensores de 10 m y lluvia. **La v6 generaliza a pistas nuevas pero pierde robustez en
condiciones extremas, y no se promueve.** No cambiamos los criterios para que pasara: es el sistema de selección
haciendo su trabajo. La v6 queda en el catálogo y la web permite compararlas en el Puerto.

**Segunda semilla: ¿las pistas, el computador o la semilla?** La v6 se entrenó en un Mac. Repetimos la v6 y el control
con la semilla 1 en GitHub Actions, con la misma configuración, y los medimos en las pistas de entrenamiento (sin la
Sierra, ya usada).

| Modelo | Mónaco seco / lluvia | Bosque | Puerto | Extremos | Peor prueba | Selección |
|---|---|---|---|---|---|---|
| v6 semilla 0 (Mac) | 100 / 100 %, 69.8 s | 100 / 100 % | 100 / 100 % | 79.2 % | diluvio 0 % | rechazada |
| **v6 semilla 1** (Actions) | **100 / 100 %, 80.4 s** | **100 / 100 %** | **100 / 100 %** | **100 %** | **100 %** | **aceptada, 7 de 7** |
| Control semilla 1 (Actions) | 100 / 100 %, 81.5 s | **0 / 0 %** | 100 / **0 %** | 94.7 % | sensores cortos con lluvia 0 % | rechazada |

1. **Practicar en tres pistas da un resultado estable entre semillas; practicar solo en Mónaco, no:** el control semilla 1
   no completa el Bosque.
2. **La caída de la v6 semilla 0 no viene de las pistas ni del Mac:** la semilla 1 da 100 % en extremos, y el control
   semilla 0, entrenado en el mismo Mac, da 98 %.
3. **Lo que distingue a la semilla 0** es que afinó con PPO hasta el final y es 10.6 s más rápida. La hipótesis es que
   afinar mucho cambia robustez por velocidad; con dos semillas no está comprobado.

La v6 semilla 1 pasó los criterios del 1 de noviembre sin tocarlos, pasó su test reservado y se promovió. El
historial conserva la v5 semilla 1 para el rollback.

## MLOps

| Requisito | Cómo se cumple |
|---|---|
| Versionamiento | Git, DVC con dos remotos y etiquetas por modelo |
| Recuperación | Manifiestos con SHA-256 y adaptadores; v1, v2 y v4 reproducen sus resultados |
| Experimentos | MLflow local y copia en DagsHub, con runs interrumpidos conservados |
| Pipeline | DVC por etapas y Prefect para validar, probar, seleccionar y publicar. `dvc status` limpio: las etapas afectadas por el experimento v6 y por la moto se comprobaron sin reentrenar (métricas idénticas al volver a correrlas) |
| Monitoreo | La API reporta versión servida, episodios, errores, fallos por causa y latencia |
| Rollback, rechazo y promoción | Probado v5 → v4 → v5, comprobando la versión que sirve la API. La v6 semilla 0 fue rechazada por los criterios; la semilla 1 los pasó y se promovió, con la v5 semilla 1 lista para rollback |
| Despliegue | Web y API en Vercel, en la misma URL, con selector de pista (la Sierra responde 403). La API es una función de Python: mismo ambiente, PPO en numpy verificado contra PyTorch. El contenedor se construye y se prueba en GitHub Actions en cada push |

## Límites

- **La v6 semilla 1 no tiene prueba en una pista que nunca vio:** para ella el Bosque y el Puerto son de
  entrenamiento, y la Sierra ya se usó con la semilla 0. Sabemos que la v6 semilla 0 generaliza, no la semilla 1.
- **Robustez a cambio de velocidad:** la recomendada es 11.8 s más lenta en seco que la v5 semilla 1 y casi igual
  al maestro (80.8 s). Los criterios no premian el tiempo por debajo del máximo.
- **Dos semillas de la v6, de las cuales una pasa:** no es la regla de tres semillas de la v5. Cuatro pistas de la
  misma familia (rectas y arcos de radio constante).
- **En la URL pública, PPO corre en numpy.** Se verificó contra PyTorch (diferencia máxima 1e-5 en las acciones),
  pero no es la misma biblioteca del entrenamiento. El contenedor sí usa PyTorch.
- **El monitoreo de la API publicada es por instancia:** Vercel puede tener varias instancias y reiniciarlas; cada
  respuesta dice desde cuándo cuenta la suya.
- **Q-learning pierde resolución** al discretizar: el ruido de sensores supera el tamaño de las celdas y lo deja entre 9 y 35 %.
- **La nota de velocidad segura es información ya procesada.** No medimos cuánto depende el agente de ella.
- **Las tablas Q anteriores a la v6** usan otra discretización y quedan solo como evidencia.
- **Modelos con adaptador:** v1 y v2 reproducen su resultado en seco con diferencias de 0.2 a 0.5 s.

## Segundo vehículo: moto MotoGP

`AutonomousRallyMoto-v0` (versión `moto-0.1`) usa el mismo circuito, puertas y recompensa con otra física: gira
inclinándose (a_lat = g·tan φ), la inclinación cambia a lo sumo 80 °/s y pasarse del agarre 0.3 s seguidos la tira
(`caida`). Observa 26 valores: los 24 del carro más la inclinación y el riesgo de caída. Sus criterios se fijaron
antes de entrenar y tiene su propio recomendado, historial y decisiones en `manifests/moto/`.

| Versión | Seco | Lluvia | Extremos | Decisión |
|---|---|---|---|---|
| `ppo-moto-v1` | 100 %, 78.2 s | 100 %, 110.0 s | 98.1 % | Aceptada y recomendada |
| `qlearning-moto-v1` | 0 % | 96 % | 40.4 % | Rechazada: su discretización no ve la inclinación |

Un modelo de un vehículo pedido en el otro responde 409 en la API, porque sus contratos son distintos (24 contra 26
observaciones). La física del carro no cambió: misma huella en 100 000 pasos y métricas idénticas.

## Pendiente antes de la entrega

- Intercambio de la ficha con otro equipo.
- Nombre del equipo y contribuciones.

## Contribuciones

_Por completar por el equipo._ Cada integrante debe poder explicar el contrato del ambiente, el versionamiento y
cómo desplegar y reproducir la solución. Usamos asistentes de código y verificamos lo generado con pruebas y métricas.

## Siguiente hipótesis razonable

La hipótesis de entrenar en varias pistas para manejar una que nunca vio ya se probó con la v6 y se cumplió.
La v6 semilla 1 mostró además que no hace falta sacrificar los extremos. La siguiente: una tercera semilla de la v6
y una quinta pista reservada (de otra familia, con curvas de radio variable) dirían si la v6 semilla 1 también
generaliza y si afinar mucho con PPO cambia robustez por velocidad. Se mediría con los mismos criterios, sin
cambiarlos.
