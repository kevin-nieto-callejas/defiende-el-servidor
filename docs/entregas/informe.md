# Informe: Autonomous Rally

Proyecto final de MLOps · Universidad Externado de Colombia · Docente: Julián Zuluaga
Equipo: _______ · Integrantes: Kevin Nieto, Miguel Melo y Allison Loango · Versión de borrador: 10 nov 2026

## Resumen

Entrenamos un agente que completa un circuito de 1 048.6 m inspirado en Mónaco, pasando seis checkpoints en
orden. En un test reservado, corrido una sola vez con semillas fuera del repositorio, el modelo recomendado (PPO
v5 semilla 1) completó el 100 % de las vueltas en seco y con lluvia, y el 99.9 % en promedio en 19 condiciones más
difíciles. Cada versión se puede identificar por su manifiesto, recuperar y evaluar con su ambiente compatible.
Conservamos también los intentos fallidos.

El resultado más útil no fue un número sino una corrección: la v4 ya daba 100 % en la evaluación oficial y aun
así chocaba en los experimentos del visor. La evaluación solo cubría los parámetros base.

Después probamos si el agente sabe manejar o memorizó Mónaco, con tres pistas nuevas y una reservada. El modelo
recomendado da 0 % en dos pistas que el piloto maestro sí completa: memorizó el circuito. Una versión entrenada en
tres pistas (v6) completa el 100 % en la pista reservada, pero no pasó nuestros criterios de selección porque
pierde aguante en condiciones extremas de Mónaco. La recomendada sigue siendo la v5 semilla 1.

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
| **`ppo-modelo-v5-s1`** | Conocer el carro y practicar todos los deslizadores con ruido | **100 %** | **100 %** | **Recomendado** |
| `ppo-modelo-v6-pistas` | Practicar en tres pistas permite manejar en una que nunca vio | 100 % | 100 % | Hipótesis cumplida; rechazado por la selección |

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
| **PPO v5 semilla 1** | **100 %, 68.6 s** | **100 %, 89.3 s** | **99.9 %** | Diluvio 98 % |
| Q-learning v8 semilla 1 | 99 %, 81.0 s | 99 %, 106.9 s | 84.8 % | Ruido 14 y 11 %, diluvio 60 % |

Casi igual a lo medido al seleccionar, así que no hay señales de que elegir la semilla haya inflado los números.

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
| PPO v5 semilla 1 (recomendado) | 100 / 100 % | **0 / 0 %** | **0 / 0 %** |
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

## MLOps

| Requisito | Cómo se cumple |
|---|---|
| Versionamiento | Git, DVC con dos remotos y etiquetas por modelo |
| Recuperación | Manifiestos con SHA-256 y adaptadores; v1, v2 y v4 reproducen sus resultados |
| Experimentos | MLflow local y copia en DagsHub, con runs interrumpidos conservados |
| Pipeline | DVC por etapas y Prefect para validar, probar, seleccionar y publicar |
| Monitoreo | La API reporta versión servida, episodios, errores, fallos por causa y latencia |
| Rollback y rechazo | Probado v5 → v4 → v5, comprobando la versión que sirve la API. La v6 fue rechazada por los criterios |
| Despliegue | Web y API en Vercel, en la misma URL, con selector de pista (la Sierra responde 403). La API es una función de Python: mismo ambiente, PPO en numpy verificado contra PyTorch. El contenedor se construye y se prueba en GitHub Actions en cada push |

## Límites

- **El modelo recomendado memorizó Mónaco:** da 0 % en el Puerto y la Sierra. La v6 maneja en pistas nuevas pero
  no aguanta los extremos. Hoy no tenemos un modelo que haga las dos cosas.
- **Una semilla por modelo en el experimento v6,** y cuatro pistas de la misma familia (rectas y arcos de radio
  constante).
- **En la URL pública, PPO corre en numpy.** Se verificó contra PyTorch (diferencia máxima 1e-5 en las acciones),
  pero no es la misma biblioteca del entrenamiento. El contenedor sí usa PyTorch.
- **El monitoreo de la API publicada es por instancia:** Vercel puede tener varias instancias y reiniciarlas; cada
  respuesta dice desde cuándo cuenta la suya.
- **Q-learning pierde resolución** al discretizar: el ruido de sensores supera el tamaño de las celdas y lo deja entre 9 y 35 %.
- **La nota de velocidad segura es información ya procesada.** No medimos cuánto depende el agente de ella.
- **Las tablas Q anteriores a la v6** usan otra discretización y quedan solo como evidencia.
- **Modelos con adaptador:** v1 y v2 reproducen su resultado en seco con diferencias de 0.2 a 0.5 s.

## Pendiente antes de la entrega

- Intercambio de la ficha con otro equipo.
- Nombre del equipo y contribuciones.
- Q-learning quedó desactualizado en DVC porque cambiaron las demostraciones del experto; falta decidir si se
  reentrena o se deja documentado.

## Contribuciones

_Por completar por el equipo._ Cada integrante debe poder explicar el contrato del ambiente, el versionamiento y
cómo desplegar y reproducir la solución. Usamos asistentes de código y verificamos lo generado con pruebas y métricas.

## Siguiente hipótesis razonable

La hipótesis anterior (entrenar en varias pistas para manejar una que nunca vio) ya se probó con la v6 y se
cumplió. La siguiente: la v6 eligió su mejor punto del entrenamiento mirando solo sus pistas. Si se elige mirando
también las pruebas extremas, y con varias semillas, un modelo debería completar la Sierra y volver a pasar el
diluvio. Se mediría con los mismos criterios de selección, sin cambiarlos.
