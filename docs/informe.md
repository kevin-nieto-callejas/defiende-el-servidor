# Informe: Autonomous Rally

Proyecto final de MLOps · Universidad Externado de Colombia · Docente: Julián Zuluaga
Equipo: _______ · Integrantes: Kevin Nieto y Miguel · Versión de borrador: 1 nov 2026

## Resumen

Entrenamos un agente que completa un circuito de 1 048.6 m inspirado en Mónaco, pasando seis checkpoints en
orden. El modelo recomendado, PPO v5, completa el 100 % de las vueltas en seco y con lluvia, y el 99.1 % en
promedio en 19 condiciones más difíciles. Cada versión se puede identificar por su manifiesto, recuperar y
evaluar con su ambiente compatible. Conservamos también los intentos fallidos.

El resultado más útil no fue un número sino una corrección: la v4 ya daba 100 % en la evaluación oficial y aun
así chocaba en los experimentos del visor. La evaluación solo cubría los parámetros base.

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
| **`modelo-v5`** | Conocer el carro y practicar todos los deslizadores con ruido | **100 %** | **100 %** | **Recomendado** |

Q-learning con tabla: de 0 % en las primeras versiones a 60 % / 15 % (v6) y 87 % / 81 % (v7).

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

| Condición (100 vueltas) | PPO v5 | Q-learning v7 |
|---|---|---|
| Seco | 100 %, 75.9 s | 87 %, 81.3 s |
| Lluvia | 100 %, 92.0 s | 81 %, 107.7 s |
| Sensores con ruido y lluvia | 100 % | 0 % |
| Pista de 6 m con lluvia | 100 % | 34 % |
| Diluvio μ 0.4 | 82 % | 36 % |
| Carro lento | 100 % | 24 % |

**Costo de la mejora:** frente a la v4, la v5 cede 0.3 s en seco y 0.2 s con lluvia.

## MLOps

| Requisito | Cómo se cumple |
|---|---|
| Versionamiento | Git, DVC con dos remotos y etiquetas por modelo |
| Recuperación | Manifiestos con SHA-256 y adaptadores; v1, v2 y v4 reproducen sus resultados |
| Experimentos | MLflow local y copia en DagsHub, con runs interrumpidos conservados |
| Pipeline | DVC por etapas y Prefect para validar, probar, seleccionar y publicar |
| Monitoreo | La API reporta versión servida, episodios, errores, fallos por causa y latencia |
| Rollback | Probado v5 → v4 → v5, comprobando la versión que sirve la API |
| Despliegue | Web en Vercel; API pendiente de acordar con el docente |

## Límites

- **Un solo circuito.** Medimos robustez ante condiciones, no manejo en un trazado desconocido.
- **La web pública está en modo replay** hasta acordar dónde vive la API. Falta la evaluación en vivo desde la URL.
- **El contenedor de la API no se ha construido** en este equipo.
- **Q-learning pierde resolución** al discretizar: el ruido de sensores supera el tamaño de las celdas y lo lleva a 0 %.
- **La nota de velocidad segura es información ya procesada.** No medimos cuánto depende el agente de ella.
- **Las tablas Q anteriores a la v6** usan otra discretización y quedan solo como evidencia.
- **Modelos con adaptador:** v1 y v2 reproducen su resultado en seco con diferencias de 0.2 a 0.5 s.

## Pendiente antes de la entrega

- Resultados de las semillas 1 y 2 de los finalistas.
- Test final reservado, una sola vez, con los modelos ya elegidos.
- Intercambio de la ficha con otro equipo.

## Contribuciones

_Por completar por el equipo._ Cada integrante debe poder explicar el contrato del ambiente, el versionamiento y
cómo desplegar y reproducir la solución. Usamos asistentes de código y verificamos lo generado con pruebas y métricas.

## Siguiente hipótesis razonable

Si se entrena en varias pistas generadas al azar, el agente debería completar un circuito que nunca vio. Se
mediría con una pista reservada. Es la limitación más importante de este trabajo.
