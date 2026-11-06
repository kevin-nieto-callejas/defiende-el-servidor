# Autonomous Rally: resumen general del proyecto

**Lee este archivo primero.** Está escrito para quien llega al proyecto sin contexto. Explica qué se pidió, cómo
funciona todo, qué hicimos día por día, qué resultados hay, dónde está cada cosa, qué falta y cómo responder las
preguntas de la sustentación. Si después de leerlo te queda una duda, revisa la sección 16, de preguntas frecuentes.

Última actualización: 5 de noviembre de 2026, sobre el commit `97c1dc4` de `main` más los cambios de la API en Vercel.

## Contenido

1. En un minuto
2. El curso y el equipo
3. Qué pide el enunciado y cómo vamos frente a la rúbrica
4. El ambiente: la pista, el carro y las reglas
5. Los dos agentes y los pilotos de referencia
6. Historia completa del proyecto, día por día
7. Resultados
8. El ciclo de MLOps, pieza por pieza
9. La web
10. La API
11. Mapa del repositorio
12. Comandos más usados
13. El computador, el calor y la operación nocturna
14. Lo que falta
15. Límites que hay que decir en la sustentación
16. Preguntas frecuentes del equipo
17. Preguntas probables del docente
18. Glosario
19. Enlaces

---

## 1. En un minuto

Es el proyecto final de MLOps de la Universidad Externado. Entrenamos un carro autónomo que da una vuelta a un
circuito inspirado en Mónaco, pasando seis checkpoints en orden, sin chocar, en seco, con lluvia y con
perturbaciones. Además construimos el ciclo completo para que cada resultado se pueda revisar, reproducir y deshacer.

| Dato | Valor |
|---|---|
| Modelo recomendado | `ppo-modelo-v5-s1`: red neuronal PPO, versión 5, semilla 1 |
| Resultado en el test reservado | 100 % de vueltas en seco (68.6 s), 100 % con lluvia (89.3 s), 99.9 % en 19 pruebas extremas |
| Segundo agente | `qlearning-modelo-qlearning-v8-s1`: tabla Q, 99 % en seco, 99 % con lluvia, 84.8 % en extremos |
| Avance estimado frente a la rúbrica | Cerca del 91 % (estimación del equipo, no una medición) |
| Lo que más falta | Datos del equipo, acceso a DagsHub, respuestas del docente y ensayo |
| Web pública | https://autonomous-rally.vercel.app (simula en vivo en `/api` desde el 6 de noviembre) |
| Pruebas automáticas | 60 (59 pasan y 1 se activa cuando existe el paquete de Vercel) |
| Versiones de modelos con manifiesto | 16 |

**Nota sobre el nombre:** el repositorio se llama `defiende-el-servidor` porque empezó con otro proyecto. Ese plan
quedó guardado en [antecedentes/](antecedentes/defiende-el-servidor.md) y ya no aplica. Todo lo actual es
Autonomous Rally.

---

## 2. El curso y el equipo

| Dato | Valor |
|---|---|
| Curso | MLOps, Universidad Externado de Colombia, 2026-II |
| Docente | Julián Zuluaga |
| Integrantes | Kevin Nieto, Miguel Melo y un tercer integrante, por completar |
| Nombre del equipo | Por completar en la ficha, el informe y la portada de la presentación |
| Repositorio oficial | https://github.com/melo11miguel/defiende-el-servidor (de Miguel) |
| Fork para Vercel | `kevin-nieto-callejas/defiende-el-servidor`, rama `ambiente-v0.4` |
| Cuentas externas | DagsHub y Hugging Face están a nombre de Kevin; Vercel también |

El curso entregó fichas de ambientes y al equipo le correspondió **Autonomous Rally**. La imagen original de la
ficha está en [ficha-autonomous-rally.png](ficha-autonomous-rally.png).

---

## 3. Qué pide el enunciado y cómo vamos frente a la rúbrica

El enunciado pide tres cosas: un ambiente de aprendizaje por refuerzo bien definido, dos agentes y un ciclo de
MLOps verificable. La prueba final es que el docente pueda **abrir una URL, elegir un modelo histórico y evaluarlo
con el ambiente compatible con ese modelo**.

### 3.1 Rúbrica

| Criterio | Peso | Estado | Qué falta |
|---|---:|---|---|
| Versionamiento y recuperación | 30 % | Casi completo | Que el docente pueda entrar a DagsHub: hoy pide iniciar sesión |
| Diseño experimental y análisis | 25 % | Casi completo | Nada técnico; ensayar la explicación |
| Pipeline, despliegue, monitoreo y rollback | 20 % | Casi completo | Desplegar el paquete de la API y evaluar desde la URL |
| Ambiente y agente | 10 % | Completo | Intercambiar la ficha con otro equipo |
| Defensa, informe y presentación | 15 % | Material listo | Nombres, contribuciones y ensayo |

### 3.2 Requisito por requisito

| Requisito del enunciado | Estado | Evidencia |
|---|---|---|
| Ficha del ambiente con misión, variables, recompensa, fin y métricas | Listo | [ambiente-v0.1.md](ambiente-v0.1.md) |
| Tres niveles de dificultad | Listo: N1, N2 y N3 | Sección 4.7 y la ficha |
| Cinco transiciones calculadas a mano | Listo y verificado por pruebas | Ficha, sección "Cinco transiciones" |
| Dos agentes: uno tabular y uno con red | Listo: Q-learning y PPO | `src/rally/agentes/` |
| Incidente, degradación e intervención | Listo: lluvia μ 0.9 → 0.5 | Sección 7.5 y el [informe](entregas/informe.md) |
| Versionar código, datos y modelos | Listo: Git, DVC y etiquetas | `dvc.yaml`, `dvc.lock`, `git tag` |
| Registro de experimentos | Listo: MLflow local y DagsHub | Sección 8.3 |
| Manifiesto por versión con SHA-256 | Listo: 16 manifiestos | [manifests/](../manifests/) |
| Recuperar modelos viejos con su ambiente | Listo: adaptadores validados | Sección 8.5 |
| Hipótesis antes de entrenar | Listo desde la familia 0.4; v1 a v4 marcadas como escritas después | `params.yaml`, MLflow |
| Criterios de selección fijos | Listo | [configs/seleccion.yaml](../configs/seleccion.yaml) |
| Tres semillas por finalista | Listo | `metrics/semillas*.json` |
| Test reservado, usado una sola vez | Listo | `metrics/test-final.json` |
| Orquestador | Listo: Prefect, probado completo con entrenamiento | [evidencia/flujo-completo/](evidencia/flujo-completo/) |
| Promoción y rollback | Listo: probado v5 → v4 → v5 | [manifests/historial.json](../manifests/historial.json) |
| Monitoreo | Listo en la API; en Vercel cuenta por instancia y dice desde cuándo | `/api/monitoreo` |
| Web pública en Vercel | Lista; detecta la API y, si no responde, entra en replay diciendo por qué | https://autonomous-rally.vercel.app |
| API pública | **Publicada**: función de Vercel en la misma URL, gratis, con los modelos reales. Probada desde la URL: lluvia, deslizadores, semillas y evaluar | `web/api/`, `deploy/api/empaquetar.py` |
| Contenedor | GitHub Actions lo construye y prueba sus rutas en cada push | `deploy/api/Dockerfile`, `.github/workflows/verificar.yml` |
| Informe | Borrador completo | [entregas/informe.md](entregas/informe.md) |
| Presentación | Lista, 14 diapositivas, sin ensayar | [entregas/presentacion/](entregas/presentacion/) |

**Son exactamente dos agentes:** Q-learning con tabla y PPO con red neuronal. Experto, prudente, maestro y aleatorio
son pilotos de referencia escritos con reglas; sirven para comparar y para enseñar, pero no son agentes entregados.

---

## 4. El ambiente: la pista, el carro y las reglas

La ficha completa está en [ambiente-v0.1.md](ambiente-v0.1.md). Aquí va lo necesario para explicarlo.

### 4.1 Misión

Dar una vuelta completa al circuito pasando los **6 checkpoints en orden** y cruzar la meta, sin chocar contra el
muro ni salirse de la pista, en el menor tiempo posible.

### 4.2 El circuito

| Dato | Valor |
|---|---|
| Largo | 1 048.6 m por la línea central, en sentido antihorario |
| Trazado | 18 curvas con nombres de Mónaco, de Sainte Dévote a Rascasse |
| Curva más cerrada | Horquilla de Fairmont, radio 9.5 m: máximo 9.2 m/s en seco y 6.8 m/s mojado |
| Ancho base | 8 m, con 2 m de zona de escape a cada lado y muro (Armco) a 6 m del centro |
| Checkpoints | CP1 después de Beau Rivage, CP2 salida del Casino, CP3 Fairmont, CP4 final del túnel, CP5 Nouvelle Chicane, CP6 Piscine |
| Mapa | [mapa-ambiente-v0.1.svg](mapa-ambiente-v0.1.svg), generado desde el código |

La suma de los giros da exactamente 360° y dos tramos no vecinos nunca están a menos de 18 m: las pruebas
automáticas lo verifican.

### 4.3 El carro y la física

- Modelo de bicicleta cinemático: 4 m de largo, 1.8 m de ancho, 2.5 m entre ejes.
- Paso de 0.1 s (10 decisiones por segundo), velocidad máxima 25 m/s (90 km/h), dirección máxima 30°.
- **Círculo de fricción:** las llantas no pueden dar más de μ·g de aceleración total. Si una curva pide más, el carro
  se abre (subviraje) y se marca derrape.
- **Consecuencia que descubrimos:** si el pedal pide todo el agarre, no queda nada para girar. Por eso con lluvia
  extrema hace falta control de tracción.
- No hay reversa.

### 4.4 Qué ve el agente: 24 números

| Grupo | Valores |
|---|---|
| Movimiento | Velocidad, giro |
| Rumbo | Dirección al siguiente checkpoint (seno y coseno), desvío del centro, error de rumbo |
| 7 rayos | Distancia al borde o al muro a −90°, −60°, −30°, 0°, 30°, 60° y 90°, divididos por 40 m fijos |
| Notas del copiloto | Curvatura de la pista a 10, 25 y 50 m |
| Agarre | Uso del agarre, derrape, agarre estimado y lluvia sí/no |
| Su carro (v0.4) | Ancho de pista, aceleración máxima, alcance de sensores |
| Velocidad segura (v0.4) | A qué velocidad conviene ir para lo que viene en los próximos 100 m |

**El agente nunca ve el agarre exacto μ.** Solo sabe si llueve y lo que miden sus llantas. Ese es el reto del
incidente.

### 4.5 Qué decide el agente

Dos controles continuos entre −1 y 1: pedal (positivo acelera, negativo frena) y dirección. Q-learning los usa
discretos: 6 posiciones de pedal × 9 de dirección = 54 acciones.

### 4.6 Recompensa y fin del episodio

| Término | Valor |
|---|---|
| Avance | +0.1 por metro de avance real sobre el máximo alcanzado |
| Checkpoint | +10 cada uno |
| Vuelta | +50 |
| Tiempo | −0.05 por paso |
| Fuera de pista | −1 por paso |
| Mando brusco | −0.2·cambio de dirección − 0.05·cambio de pedal |
| Fin malo | −50 al chocar, salir 1 s de la pista o estancarse 10 s |

Una vuelta limpia vale unos +170. El episodio termina con éxito, choque, salida, estancamiento o a los 180 s.

Las trampas cerradas por diseño, cada una con su prueba automática: cobrar dos veces un checkpoint, ir y volver
para cobrar avance, cortar camino, saltar de un tramo a otro en la horquilla, quedarse quieto para no arriesgar,
perder una puerta cruzada pisando el escape e ir en reversa.

### 4.7 Los tres niveles

| Nivel | Qué cambia | Modelos |
|---|---|---|
| N1 · Misión base | Seco, parámetros base | `modelo-v1`, `modelo-v2` |
| N2 · Más decisiones | Seco y lluvia sin ver μ | `experimento-v3`, `modelo-v4`, `modelo-qlearning-v6` |
| N3 · Operación exigente | μ 0.4–1, ancho 6–12 m, aceleración 2–6, sensores 10–40 m y ruido | Familia 0.4: PPO v5 y Q-learning v7 y v8 |

Los gráficos no cuentan como dificultad: cambian las reglas y lo que el agente debe decidir.

### 4.8 Versiones del ambiente

| Versión | Qué cambió | Observaciones |
|---|---|---|
| Pista rectangular | Primera prueba, 239 m y 3 checkpoints | — |
| 0.1-monaco | Circuito de Mónaco y notas del copiloto | 16 |
| 0.2 | Sensor de agarre y correcciones de una revisión de código | 19 |
| 0.3 | Sensor de lluvia y mitad del entrenamiento con lluvia | 20 |
| **0.4** | El agente conoce su carro, rayos en escala fija, velocidad segura | **24** |

Cada modelo guarda en su manifiesto con qué versión del ambiente se entrenó. Los modelos de 16, 19 y 20
observaciones corren hoy con un adaptador (sección 8.5).

---

## 5. Los dos agentes y los pilotos de referencia

### 5.1 PPO (red neuronal), el recomendado

- Biblioteca Stable-Baselines3. Red de dos capas de 256 neuronas. 3 millones de pasos con 12 ambientes en paralelo.
- **Primero imita, después practica.** Copiar vueltas perfectas falló (v3): al primer error la red llegaba a
  situaciones que nunca había visto. La solución fue **DAgger**: la red maneja, el piloto maestro dice qué habría
  hecho en cada situación, y la red aprende de esas correcciones durante 20 rondas. Después PPO afina con prueba y
  error.
- **Dominio aleatorio:** en cada episodio sortea agarre, ancho, aceleración y alcance de sensores. El 30 % de los
  episodios usa la configuración base de la ficha.
- **Ruido en sensores** de hasta 4 % mientras entrena, para que no dependa de lecturas perfectas.

### 5.2 Q-learning (tabla)

- Una tabla con 117 600 situaciones × 54 acciones. La situación se arma agrupando desvío, error de rumbo,
  velocidad, curvatura a 10 y 25 m, lluvia y margen de frenada.
- También empieza con DAgger (50 rondas) y luego hace 600 episodios de Q-learning.
- En la tabla, el pedal significa m/s² y no porcentaje, para que sirva con cualquier carro.
- **Su límite:** al agrupar pierde resolución. Con ruido de 3 % en los sensores, las lecturas saltan de celda y el
  agente se confunde: completa entre 9 y 35 % de las vueltas en esas pruebas.

### 5.3 Pilotos de referencia (no son agentes)

| Piloto | Qué hace | Para qué sirve |
|---|---|---|
| Experto | Sigue la pista suponiendo piso seco | Línea base: 100 % en seco, 0 % con lluvia |
| Prudente | Maneja como si siempre lloviera | Muestra el costo de ir lento: 96.7 s en seco |
| Maestro | Experto con control de tracción y según el clima | Es quien enseña en DAgger |
| Aleatorio | Mandos al azar | Piso de comparación |

---

## 6. Historia completa del proyecto, día por día

El detalle de cada decisión está en la [bitácora](registro/bitacora.md) y en los commits.

| Fecha | Qué pasó |
|---|---|
| 23 oct | Miguel crea el repositorio para *Defiende el servidor*. El curso asigna Autonomous Rally |
| 28 oct | Ficha del ambiente, circuito de Mónaco y `modelo-v1`: 100 % en seco, 0 % con lluvia |
| 29 oct | `modelo-v2` con sensor de agarre: más rápido en seco (63.1 s), igual de malo con lluvia |
| 29 oct | `experimento-v3`: imitar vueltas perfectas da 0 % en todo. Rechazado y conservado como evidencia |
| 29 oct | `modelo-v4` con DAgger: 100 % en seco y con lluvia. Primer modelo aceptado del incidente |
| 30 oct | Visor 3D estilo transmisión. Q-learning con DAgger tabular (v6): 60 % y 15 % |
| 1 nov | Revisión contra el enunciado: faltaban Vercel, manifiestos, orquestador, rollback, semillas y test reservado |
| 1 nov | Hallazgo del 100 % engañoso: la v4 daba 0 % en 11 de 35 combinaciones de los deslizadores |
| 1 nov | Ambiente 0.4, PPO v5, Q-learning v7 y v8, API, web en Vercel, manifiestos, Prefect, rollback |
| 1 nov | Apagón por calor a las 19:50 con 12 núcleos. Se bajó a 7 y se desactivó el Turbo |
| 1 nov | Tres semillas, selección de finalistas y test reservado, corrido una sola vez a las 21:57 |
| 1 nov | Revisión de la web: avisos, celular, cámara TV, pantalla de carga y reflejo del piso |
| 2 nov | Flujo completo de Prefect con entrenamiento real: reprodujo los resultados sin diferencias |
| 3 nov | Este resumen ampliado |

### 6.1 Los tres aprendizajes que hay que contar

1. **Un 100 % puede engañar.** La v4 daba 100 % en la evaluación oficial. El equipo vio choques al mover los
   deslizadores del visor, y al medir 35 combinaciones la v4 dio 0 % en 11 y 85 % en una. Causa: los rayos se
   dividían por su alcance, así que cambiar el alcance cambiaba el significado de cada lectura; y el agente no
   conocía su carro. Por eso nació el ambiente 0.4 y el nivel N3.
2. **El problema de la lluvia extrema era físico.** Con μ 0.4 ningún piloto terminaba la vuelta. No era por ir
   rápido: el pedal gastaba todo el agarre y no quedaba para girar. El control de tracción lo resolvió, y es lo que
   ahora aprenden los agentes del maestro.
3. **Una sola semilla engaña.** La semilla 0 de PPO v5, promovida primero, resultó la más lenta y la menos robusta
   de las tres.

---

## 7. Resultados

Todas las cifras son % de vueltas completas sobre 100 episodios, y tiempo mediano de las vueltas completas.

### 7.1 Evolución de PPO

| Versión | Hipótesis | Seco | Lluvia | Decisión |
|---|---|---|---|---|
| `modelo-v1` | Primer modelo, entrenado en seco | 100 %, 77.6 s | 0 % | Reemplazada |
| `modelo-v2` | Un sensor de agarre ayuda con lluvia | 100 %, 63.1 s | 0 % | Reemplazada: no ayudó |
| `experimento-v3` | Practicar con lluvia e imitar vueltas | 0 % | 0 % | Rechazada |
| `modelo-v4` | DAgger corrige los errores de la red | 100 %, 75.6 s | 100 %, 91.8 s | Aceptada y luego reemplazada |
| **`ppo-modelo-v5-s1`** | Conocer el carro y practicar todo con ruido | **100 %, 68.6 s** | **100 %, 89.3 s** | **Recomendada** |

### 7.2 Evolución de Q-learning

| Versión | Seco | Lluvia | Qué cambió |
|---|---|---|---|
| v1 a v4 | 0 % | 0 % | Tabla aprendiendo sola: no llegaba a la parte difícil |
| v6 | 60 % | 15 % | DAgger tabular |
| v7 | 87 % | 81 % | Ambiente 0.4 y margen de frenada |
| **v8 semilla 1** | **100 %, 81.0 s** | **100 %, 106.9 s** | Practicó carros lentos y ruido; aquí el refuerzo sí mejoró la imitación |

### 7.3 Contraste de tres semillas

Tres entrenamientos independientes por agente, misma suite: semillas 0–99 y 19 pruebas extremas.

| Modelo | Semilla | Seco | Lluvia | Extremos | Peor prueba |
|---|---|---|---|---|---|
| PPO v5 | 0 | 100 %, 75.9 s | 100 %, 92.0 s | 98.5 % | Diluvio 71 % |
| **PPO v5** | **1** | **100 %, 68.6 s** | **100 %, 89.3 s** | **100 %** | Ninguna bajo 100 % |
| PPO v5 | 2 | 100 %, 69.9 s | 100 %, 85.1 s | 99.8 % | Diluvio 96 % |
| Q-learning v8 | 0 | 99 %, 81.1 s | 100 %, 107.6 s | 85.0 % | Ruido y lluvia 10 % |
| **Q-learning v8** | **1** | **100 %, 81.0 s** | **100 %, 106.9 s** | **85.9 %** | Ruido y lluvia 9 % |
| Q-learning v8 | 2 | 95 %, 80.7 s | 98 %, 107.4 s | 81.9 % | Ruido y lluvia 16 % |

PPO: 100 % ± 0 en seco y lluvia; en diluvio, 89 % ± 12.8. Q-learning: 98.0 % ± 2.2 en seco y 99.3 % ± 0.9 con lluvia.
La semilla 1 de PPO le gana a la 2 por 0.2 puntos, dentro del ruido; la 2 es 4 s más rápida con lluvia.

### 7.4 Test reservado: la medida honesta

Elegir la mejor de tres semillas con la misma suite favorece a la ganadora. Por eso hay un test reservado:
100 semillas que **no están en el repositorio** (solo en el `.env` de Kevin; se publica su SHA-256), corrido **una
sola vez** el 1 de noviembre a las 21:57, con los modelos ya elegidos.

| Condición | PPO v5 semilla 1 | Q-learning v8 semilla 1 |
|---|---|---|
| Seco (μ 0.9) | 100 %, 68.6 s | 99 %, 81.0 s |
| Lluvia (μ 0.5) | 100 %, 89.3 s | 99 %, 106.9 s |
| Llovizna (μ 0.65) | 100 % | 97 % |
| Casi seco (μ 0.72) | 100 % | 100 % |
| Más agarre (μ 1.1) | 100 % | 96 % |
| Salida torcida, seco / lluvia | 100 / 100 % | 80 / 97 % |
| Ruido en sensores 3 %, seco / lluvia | 100 / 100 % | **14 / 11 %** |
| Diluvio (μ 0.4) | **98 %** | **60 %** |
| Límite de lluvia (μ 0.75) | 100 % | 97 % |
| Pista de 6 m, seco / lluvia | 100 / 100 % | 98 / 67 % |
| Pista de 12 m, seco / lluvia | 100 / 100 % | 100 / 100 % |
| Sensores de 10 m, seco / lluvia | 100 / 100 % | 99 / 99 % |
| Sensores de 40 m, seco / lluvia | 100 / 100 % | 99 / 99 % |
| Carro lento (a_max 2) | 100 % | 99 % |
| Carro rápido con lluvia (a_max 6) | 100 % | 99 % |
| **Promedio de las 19 pruebas extremas** | **99.9 %** | **84.8 %** |

Casi igual a lo medido al seleccionar (PPO 100 → 99.9 %, Q-learning 85.9 → 84.8 %): no hay señales de que elegir la
semilla haya inflado los números. **El test ya se usó y no se debe repetir.**

### 7.5 El incidente

**Incidente:** el asfalto se moja y la adherencia baja de μ 0.9 a 0.5, sin cambiar nada más.

| Paso | Qué pasó |
|---|---|
| Degradación | El experto pasa de 100 % a 0 %. v1 y v2 también |
| Primera intervención (v4) | DAgger resuelve la condición oficial: 100 % / 100 % |
| Segunda degradación | La encontramos nosotros: la v4 cae en 11 de 35 combinaciones de deslizadores |
| Segunda intervención (v5) | Configuración visible, rayos en escala fija, práctica en todo el rango y control de tracción |

| Condición | PPO v4 | PPO v5 semilla 1 | Q-learning v8 semilla 1 |
|---|---|---|---|
| Seco | 100 %, 75.6 s | 100 %, 68.6 s | 100 %, 81.0 s |
| Lluvia | 100 %, 91.8 s | 100 %, 89.3 s | 100 %, 106.9 s |
| Ruido y lluvia | 63 % | 100 % | 9 % |
| Diluvio μ 0.4 | 0 % | 100 % | 52 % |

La columna de la v4 usa las semillas 1000–1099 en las dos últimas filas; las otras, las semillas 0–99.

Criterio de aceptación de la ficha: con lluvia debe completar más vueltas que el modelo base, y en seco no puede
perder más de 5 puntos ni subir más de 5 % su tiempo. PPO v5 semilla 1 cumple y además mejora en tiempo.

### 7.6 Referencias

| Piloto | Seco | Lluvia |
|---|---|---|
| Experto | 100 %, 77.4 s | 0 % |
| Prudente | 100 %, 96.7 s | 100 %, 96.8 s |
| Maestro | 100 %, 80.8 s | 100 %, 103.8 s |
| **PPO v5 semilla 1** | **100 %, 68.6 s** | **100 %, 89.3 s** |

El agente final le gana en tiempo al piloto que le enseñó: 12 s en seco y 14 s con lluvia.

---

## 8. El ciclo de MLOps, pieza por pieza

```
params.yaml (hipótesis y parámetros)
      │
      ▼
dvc repro ──► datos → qlearning → ppo → evaluar → registrar → generalizacion
      │              (cada etapa queda en dvc.lock; los pesos en DagsHub y en un almacén local)
      ├─► MLflow: runs, métricas y registro de modelos (local y copia en DagsHub)
      ▼
rally manifiesto ──► manifests/: identidad, SHA-256, contrato, ambiente y resultados
      │
      ▼
rally seleccionar ──► aplica configs/seleccion.yaml ──► promover o rechazar ──► historial.json
      │                                                      │
      ▼                                                      ▼
Prefect (pipelines/flujo.py) orquesta todo           rollback: vuelve al anterior
      │
      ▼
API (FastAPI) sirve el recomendado ──► web en Vercel (en vivo; replay si la API no responde)
```

### 8.1 Git

- Código, parámetros, métricas, manifiestos y documentación.
- Una etiqueta por versión: `ambiente-v0.1`, `modelo-v1`, `modelo-v2`, `experimento-v3`, `modelo-v4`,
  `modelo-v5`, `modelo-qlearning-v6`, `modelo-qlearning-v7`, `modelo-qlearning-v8`.
- Se trabaja en ramas y se une a `main` cuando pasan las pruebas.

### 8.2 DVC

- Etapas en [dvc.yaml](../dvc.yaml): `datos` (vueltas de demostración), `qlearning`, `ppo`, `evaluar`, `registrar`
  y `generalizacion`. `dvc repro` solo rehace lo que cambió.
- `dvc.lock` guarda el hash de cada entrada y salida: es la receta exacta de cada resultado.
- `finalistas.dvc` guarda los pesos de las semillas 1 y 2 de ambos agentes.
- Dos remotos: `dagshub` (por defecto, en la nube) y `almacen` (copia local en el PC de Kevin).
- **Bajar los modelos pide usuario y token de DagsHub**, aunque el repositorio no sea privado. Se guardan en
  `.dvc/config.local`, que no se sube a git.

### 8.3 MLflow y DagsHub

- MLflow registra cada entrenamiento: parámetros, hipótesis, métricas y si el run se interrumpió. Los runs
  interrumpidos se conservan.
- Base local `mlflow.db`; `rally sincronizar` copia los experimentos a DagsHub.
- Registro de modelos: `rally-ppo` versión 6 y `rally-qlearning` versión 9 tienen la etiqueta `@champion`.
- Experimentos: https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments (pide iniciar sesión).

### 8.4 Manifiestos

Cada versión tiene un archivo en [manifests/](../manifests/) con todo lo necesario para identificarla y
recuperarla:

| Campo | Para qué |
|---|---|
| `nombre`, `tipo`, `etiqueta_git`, `git_commit` | Qué es y de qué código salió |
| `run_id` | Su run en MLflow |
| `level_id`, `decision`, `hipotesis` | Nivel, si se aceptó y qué se quería probar |
| `environment_version`, `ambiente_huella` | Con qué ambiente se entrenó |
| `model_uri`, `model_md5_dvc`, `model_sha256` | Dónde están los pesos y cómo comprobar que son esos |
| `config_sha256`, `runtime_ref` | Parámetros y dependencias exactas |
| `seed`, `evaluation_suite_id` | Semilla y suite de evaluación |
| `contrato` | Orden de las 24 observaciones, acciones, recorte y paso de tiempo |
| `resultados` | Vueltas, tiempos, incidentes y recompensa en seco y lluvia |

Además: `catalogo.json` (lista para la web), `recomendado.json` (el que sirve la API) e `historial.json` (cada
promoción y rollback con fecha y motivo).

Los 16 manifiestos: PPO v1, v2, v3, v4, v5, v5-s1 y v5-s2; Q-learning v1, v2, v3, v4, v6, v7, v8, v8-s1 y v8-s2.

### 8.5 Recuperar modelos viejos: adaptadores

Los modelos anteriores a la v0.4 esperan 16, 19 o 20 observaciones. En vez de guardar copias del ambiente viejo,
un adaptador convierte las 24 observaciones actuales al formato que cada modelo conoce (por ejemplo, vuelve a
dividir los rayos por el alcance). Se validó que v1, v2 y v4 reproducen sus resultados: en seco con diferencias de
0.2 a 0.5 s. Las tablas Q anteriores a la v6 usan otra discretización y quedan solo como evidencia: la API las
marca como no ejecutables. Código: `src/rally/historicos.py`; evidencia: `docs/evidencia/modelos/`.

### 8.6 Selección, promoción y rollback

- Los criterios están en [configs/seleccion.yaml](../configs/seleccion.yaml) y **se fijaron el 1 de noviembre,
  antes de ver los resultados de la familia 0.4**.
- PPO debe tener al menos 98 % en seco y en lluvia, tiempo en seco de máximo 81.3 s (experto + 5 %), 85 % de
  promedio en extremos, ninguna prueba bajo 50 % y no perder más de 2 puntos frente al recomendado actual.
- Q-learning, con umbrales más bajos: 70 % seco, 50 % lluvia, 90 s y 40 % en extremos.
- `rally seleccionar` aplica los criterios. Si el candidato pasa y se pide `--promover`, queda como recomendado y se
  anota en el historial. `--rollback` vuelve al anterior.
- **Prueba de rollback:** v5 → v4 → v5, comprobando en cada paso qué modelo servía la API. Está en el historial.

### 8.7 Prefect

[pipelines/flujo.py](../pipelines/flujo.py) orquesta 8 etapas y deja una evidencia JSON por etapa:

| Etapa | Qué hace |
|---|---|
| 1. Validar | Revisa versión del ambiente y tamaño de la observación |
| 2. Pruebas | Corre `pytest` |
| 3. Entrenar y evaluar | `dvc repro` completo; reintenta una vez si falla |
| 4. Registrar | Regenera los manifiestos |
| 5. Seleccionar | Aplica los criterios al candidato |
| 6. Promover | Si pasa, lo deja como recomendado |
| 7. Publicar | Actualiza el catálogo y rearma el paquete de la API de Vercel |
| 8. Comprobar | Pregunta a la API qué modelo sirve |

Se probó dos veces: sin entrenar ([evidencia/flujo/](evidencia/flujo/)) y completo con entrenamiento real, en una
copia aparte, el 1 y 2 de noviembre ([evidencia/flujo-completo/](evidencia/flujo-completo/)). El reentrenamiento dio
**exactamente** los mismos resultados oficiales: 0 diferencias en 5 pilotos, 2 condiciones y 21 pruebas. El
computador se suspendió 7 horas a mitad de PPO por batería baja y el flujo siguió desde su punto de guardado.

Prefect vive en un entorno aparte (`~/.venvs/rally-flujo`) para no mezclar sus dependencias con las del
entrenamiento.

Como Vercel despliega desde git, la etapa 7 deja el paquete listo y la publicación termina con commit y push.
Después se comprueba la URL pública con `pipelines/flujo.py --comprobar https://autonomous-rally.vercel.app`.
El rollback también rearma el paquete, para que la web sirva la versión restaurada.

### 8.8 Monitoreo

La API lleva la cuenta de lo que sirve: versión del modelo y del ambiente, commit, episodios corridos, errores,
fallos por causa (choque, salida, estancado, tiempo) y latencia por paso. Se ve en `/api/monitoreo` y en el panel
del catálogo de la web. En modo replay no hay datos en vivo y la web lo dice. En Vercel cada instancia de la
función lleva su propia cuenta y se reinicia cuando Vercel la recicla; la respuesta dice desde cuándo cuenta.

### 8.9 Despliegue

| Pieza | Dónde | Estado |
|---|---|---|
| Web | Vercel, desde el fork de Kevin, carpeta `web/` | Publicada. La versión con detección de la API está en `main`, falta subirla al fork |
| API | Vercel, función de Python en `web/api/index.py`, en el mismo dominio | Publicada el 6 de noviembre con `web/api/_paquete` (modelos reales, 2.8 MB). La función pesa 191 MB, bajo el límite de 500. Hugging Face quedó descartado: los Spaces con Docker exigen PRO |
| Contenedor | `deploy/api/Dockerfile`, paquete con `deploy/api/empaquetar.py` | GitHub Actions lo construye sin pesos y prueba sus rutas en cada push. Queda como alternativa para un host con Docker |
| Modelo en Hugging Face | https://huggingface.co/Kevinnieto0001/autonomous-rally-ppo | PPO v5 semilla 1, etiqueta `v5-s1`, con manifiesto y test reservado; SHA-256 verificado al bajarlo. Las versiones anteriores siguen en las etiquetas `v1`, `v2` y `v4` |

**Por qué numpy en la API publicada:** una función de Vercel no puede cargar PyTorch, que pesa más que su límite.
La red de PPO es una red pequeña (24 entradas, dos capas de 256 con tanh y 2 salidas), así que su cuenta se
reproduce en numpy. `deploy/api/empaquetar.py --vercel` exporta los pesos y, antes de guardarlos, compara las
acciones de numpy y PyTorch en unas 7 000 observaciones: vueltas reales en seco y con lluvia y observaciones al
azar. Si alguna difiere en más de 1e-5, no se empaqueta. Cada archivo se llama con el SHA-256 del modelo original
y lo guarda adentro, así la identidad sigue siendo la del manifiesto. La API dice en cada respuesta qué motor usó
(`numpy`, `pytorch`, `tabla` o `reglas`).

**Por qué el fork:** Vercel no tiene acceso al repositorio de Miguel. Para actualizar la web hay que subir la
versión a la rama `ambiente-v0.4` del fork. El último cambio de la web es `3450fde`; lo que vino después fue solo
documentación, así que la web publicada está al día.

### 8.10 Seguridad

- Los tokens de Hugging Face y DagsHub van en `.env`; la contraseña de DVC, en `.dvc/config.local`. Ninguno de los
  dos se sube a git. La plantilla es [.env.example](../.env.example).
- La semilla del test reservado está solo en el `.env` de Kevin.
- Pendiente: rotar los tokens antes de la entrega.

---

## 9. La web

**Pública:** https://autonomous-rally.vercel.app. **Local, con API en vivo:** ver la guía y la sección 12.

### 9.1 Qué se ve

- Circuito 3D con estilo de transmisión de televisión, hecho con three.js. El visor está en `src/rally/static/` y
  lo usan tanto la web de Vercel como `rally web`.
- **Cámaras:** Persecución (1), TV (2), Aérea (3), Cabina (4), Libre (5) y Vitrina (6, gira alrededor del carro).
- **Clima:** Seco o Lluvia, con piso mojado y reflejos.
- **Deslizadores:** agarre, ancho, aceleración, alcance de sensores y semilla. "Aleatorio" sortea dentro de los
  rangos de la ficha. "Correr experimento" corre la vuelta con esos parámetros.
- **Paneles:** Telemetría, Registro de experimentos y Aprendizaje.
- **Controles:** espacio pausa, R reinicia, flechas avanzan o retroceden 2 s, H oculta paneles, Esc cierra el
  resultado. Velocidad ½×, 1×, 2× y 4×. Calidad Auto, Alta, Media o Baja.
- **Catálogo de modelos:** lista las 16 versiones con su hipótesis, decisión, ambiente y SHA-256; permite cargar,
  evaluar y comparar modelos, y muestra el monitoreo.

### 9.2 Modo replay y modo en vivo

| | Replay (si la API no responde) | En vivo (con API) |
|---|---|---|
| Qué muestra | Vueltas grabadas de antemano con la condición base | La simulación que corre la API en Python |
| Deslizadores | Avisan que hace falta la API | Corren el experimento con esos parámetros |
| Evaluar y comparar | No disponibles | Disponibles |
| Monitoreo | Sin datos | Con datos |

Al cargar, la web pregunta a `/api/salud`. Si responde, simula en vivo; si no, entra en replay y la nota del
panel dice por qué (por ejemplo, "la API respondió 500"). La primera consulta puede tardar unos segundos mientras
la función arranca.

### 9.3 Correcciones recientes de la web

- La cámara TV quedaba ciega en el túnel: ahora usa cámaras propias en ese tramo.
- El aviso de replay tapaba los instrumentos y el freno: se movió dentro del panel.
- En celular los paneles tapaban la pista: arranca con el panel plegado.
- Al recargar se veía unos segundos el carro básico: la pantalla de carga espera texturas, cielo, carro y shaders.
- La línea gris clara sobre el asfalto seco era el reflejo de la goma: ahora solo brilla con lluvia.
- Rendimiento medido: 31 FPS en calidad Media; con lluvia, 27. En Alta baja a unos 11.

Falla conocida sin corregir: hacia el segundo 26, la cámara atraviesa el arco verde del CP2 y se ve un destello verde.

---

## 10. La API

FastAPI, en [src/rally/api.py](../src/rally/api.py). Simula con el mismo Python del entrenamiento: **Python es la
autoridad del mundo; el navegador solo dibuja.** Cada respuesta dice qué modelo, ambiente, commit y motor la
produjo. Publicada, corre como función de Vercel ([web/api/index.py](../web/api/index.py)): el commit es el que
Vercel desplegó y `commit_paquete` es el commit del que salió el paquete. Las versiones anteriores a la v6 de
Q-learning responden 409: se conservan solo como evidencia.

| Ruta | Qué devuelve |
|---|---|
| `GET /api/salud` | Estado, versión del ambiente, commit y modelo recomendado |
| `GET /api/monitoreo` | Episodios, errores, fallos por causa y latencia |
| `GET /api/pista` | Geometría del circuito y piloto recomendado |
| `GET /api/modelos` | Catálogo con las 16 versiones |
| `GET /api/modelos/{nombre}` | Manifiesto de una versión |
| `GET /api/episodio?piloto=...` | Una vuelta completa, cuadro por cuadro, con los parámetros pedidos |
| `POST /api/evaluar` | Evalúa un modelo en hasta 20 episodios y reporta vueltas, tiempos, fallos y si usó adaptador |

Correrla en local: `.venv/bin/rally api` (puerto 8000).

---

## 11. Mapa del repositorio

| Ruta | Contenido |
|---|---|
| `src/rally/env.py` | El ambiente Gymnasium `AutonomousRally-v0`, versión 0.4 |
| `src/rally/track.py` | El circuito de Mónaco y sus checkpoints |
| `src/rally/policies.py` | Pilotos de referencia: experto, prudente, maestro, aleatorio |
| `src/rally/agentes/ppo.py` | Entrenamiento de PPO, DAgger, dominio aleatorio y ruido |
| `src/rally/agentes/qlearning.py` y `discreto.py` | Q-learning y la discretización de la tabla |
| `src/rally/pipeline.py` | Las etapas que corre DVC |
| `src/rally/generalizacion.py` | Las 19 pruebas extremas |
| `src/rally/historicos.py` | Catálogo y adaptadores para modelos viejos |
| `src/rally/agentes/red_numpy.py` | Red de PPO en numpy y su exportación verificada contra PyTorch |
| `src/rally/manifiesto.py` | Genera los manifiestos |
| `src/rally/seleccion.py` | Criterios, promoción y rollback |
| `src/rally/semillas.py` | Contraste de tres semillas |
| `src/rally/testfinal.py` | Test reservado |
| `src/rally/api.py` | API |
| `src/rally/replays.py` | Graba las vueltas para el modo replay |
| `src/rally/cli.py` | El comando `rally` |
| `src/rally/static/` | Visor 3D |
| `web/` | Aplicación Vite + TypeScript para Vercel: catálogo, replay, evaluación |
| `pipelines/flujo.py` | Flujo de Prefect |
| `manifests/` | Manifiestos, catálogo, recomendado e historial |
| `configs/seleccion.yaml` | Criterios de selección |
| `metrics/` | Resultados oficiales, semillas y test reservado |
| `params.yaml`, `dvc.yaml`, `dvc.lock` | Parámetros, etapas y receta exacta |
| `finalistas.dvc` | Pesos de las semillas 1 y 2 |
| `deploy/api/` | Empaquetado de la API (Vercel o contenedor) y Dockerfile |
| `web/api/` | Función de Vercel con la API; `_paquete/` tiene código, manifiestos y modelos en numpy |
| `.github/workflows/verificar.yml` | Pruebas, web, paquete y contenedor en cada push |
| `scripts/` | Mediciones y automatización de la corrida final |
| `tests/` | Pruebas del ambiente, la API y la selección |
| `docs/` | Esta documentación; el índice está en [docs/README.md](README.md) |

---

## 12. Comandos más usados

La instalación completa está en la [guía para empezar](guias/empezar.md).

| Para | Comando |
|---|---|
| Instalar | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e .` |
| Correr las pruebas | `.venv/bin/pytest` |
| Bajar modelos y datos | `.venv/bin/dvc pull -r dagshub` (antes, configurar usuario y token) |
| Ver qué se reentrenaría | `.venv/bin/dvc status` |
| Entrenar sin recalentar | `taskset -c 0-5 .venv/bin/dvc repro` |
| Evaluar pilotos | `.venv/bin/rally evaluar` |
| Las 5 transiciones | `.venv/bin/rally transiciones` |
| API | `.venv/bin/rally api` → http://127.0.0.1:8000 |
| Web con API en vivo | `cd web && npm ci && npm run dev` → http://localhost:5173 |
| Web compilada | `cd web && npm run build && npx vite preview` → http://localhost:4173 |
| Visor viejo con entrenamiento en vivo | `.venv/bin/rally web` → puerto 8765 |
| Interfaz de MLflow | `.venv/bin/rally mlflow` |
| Regenerar manifiestos | `.venv/bin/rally manifiesto` |
| Aplicar criterios | `.venv/bin/rally seleccionar ppo-modelo-v5-s1 --tipo ppo --semilla 1` |
| Rollback | `~/.venvs/rally-flujo/bin/python pipelines/flujo.py --rollback "motivo"` |
| Regenerar vueltas grabadas | `.venv/bin/rally replays` |
| Copiar MLflow a DagsHub | `.venv/bin/rally sincronizar` (necesita `DAGSHUB_TOKEN`) |
| Armar la API de Vercel | `.venv/bin/python deploy/api/empaquetar.py web/api/_paquete --vercel` |
| Revisar que el paquete está al día | `.venv/bin/python deploy/api/empaquetar.py web/api/_paquete --verificar` |
| Comprobar la URL pública | `~/.venvs/rally-flujo/bin/python pipelines/flujo.py --comprobar https://autonomous-rally.vercel.app` |

La web compilada (puerto 4173) siempre entra en modo replay si se compiló sin `VITE_API_BASE_URL`. Para la
simulación en vivo en local, usa `npm run dev` (puerto 5173) con la API encendida.

**No correr `rally test-final`:** ya se usó, y repetirlo para ajustar modelos le quita su valor.

---

## 13. El computador, el calor y la operación nocturna

Todo se entrenó en el portátil de Kevin, con WSL Ubuntu en Windows.

- **Apagón por calor:** el 1 de noviembre a las 19:50 se apagó con 12 núcleos entrenando. No hubo daños; se
  perdió el avance de PPO semilla 2, que reinició. Desde ahí se usan como máximo 7 núcleos con `taskset` y el Turbo
  del procesador está desactivado. No volvió a pasar.
- **Suspensión por batería:** del 2 de noviembre a la 1:12 hasta las 8:06 el equipo se suspendió por batería baja.
  El flujo de Prefect siguió desde su punto de guardado sin perder avance.
- **Vigilante:** un script en Ubuntu revisa cada pocos minutos RAM, disco y carga, anota alertas y vuelve a levantar
  la API y la web local si se caen. Los registros de la corrida final están en
  [registro/corrida-final/](registro/corrida-final/).
- **DagsHub dio errores 502** durante las subidas: se reintentó en segundo plano hasta que funcionó.
- PPO y Q-learning guardan puntos de control: si se cortan, siguen donde iban.

**Si vas a entrenar en tu computador:** limita los núcleos con `taskset`, revisa `dvc status` antes y ten en cuenta
que PPO v5 con 3 millones de pasos tarda varias horas.

---

## 14. Lo que falta

| Tarea | Responsable | Prioridad | Depende de |
|---|---|---|---|
| Probar desde la URL: catálogo, cargar un modelo viejo y el recomendado, evaluar y comparar | Equipo | Alta | — |
| Revisar el primer resultado de GitHub Actions (pruebas, web y contenedor) | Miguel | Media | Push a su repositorio |
| Preguntar cómo revisará DagsHub, que pide iniciar sesión | Kevin | Alta | Docente |
| Confirmar que Prefect sirve como orquestador (la otra opción era Airflow) | Kevin | Media | Docente |
| Dar acceso en DagsHub a los compañeros | Kevin | Alta | — |
| Nombre del equipo, tercer integrante y contribuciones en ficha, informe y presentación | Equipo | Media | — |
| Intercambiar la ficha con otro equipo y corregir lo ambiguo | Equipo | Media | Otro equipo |
| Rotar los tokens de Hugging Face y DagsHub | Kevin | Media | — |
| Reactivar el Turbo del procesador cuando no se entrene | Kevin | Baja | — |
| Ensayar la sustentación: cada integrante debe explicar ambiente, versionamiento y despliegue | Todos | Alta | — |

**Lo técnico está terminado y publicado.** Lo que falta son las respuestas del docente y los datos del equipo.

---

## 15. Límites que hay que decir en la sustentación

- **Hay un solo circuito.** Medimos robustez ante condiciones, no manejo en una pista desconocida. Es la limitación
  más importante; la siguiente hipótesis sería entrenar en pistas generadas al azar y medir en una reservada.
- **Las 19 pruebas extremas cambian una condición a la vez.** Combinadas, el modelo falla: con diluvio y
  aceleración 6 completó 1 de 3 vueltas, y con todos los deslizadores al extremo (pista de 6 m, μ 0.4, aceleración
  6 y sensores de 10 m), 0 de 3. Medido el 3 de noviembre en la API local. Si el docente prueba eso en la web, va a
  ver el choque: hay que decirlo antes.
- **En la URL pública, PPO corre en numpy.** Se verificó contra PyTorch con una diferencia máxima de 1e-5 en las
  acciones; el contenedor sí usa PyTorch. Si la API no responde, la web muestra vueltas grabadas y lo dice.
- **El monitoreo publicado es por instancia de la función.** Vercel puede reiniciarla y la cuenta vuelve a cero.
- **Q-learning falla con ruido en sensores:** sus celdas son más finas que el ruido.
- **La nota de velocidad segura es ayuda ya procesada.** No medimos cuánto depende el agente de ella.
- **Las hipótesis de v1 a v4 y de Q-learning v6 se escribieron después de entrenar,** y están marcadas así en MLflow.
- **Los modelos viejos corren con adaptador** y reproducen su resultado con diferencias de 0.2 a 0.5 s.
- **El contenedor se prueba sin pesos en GitHub Actions.** El paquete con modelos se armó el 3 de noviembre, pero esa imagen no ha corrido en un host.

---

## 16. Preguntas frecuentes del equipo

**¿Qué modelo presentamos?**
`ppo-modelo-v5-s1`. Es el recomendado en `manifests/recomendado.json` y el `@champion` de `rally-ppo` en MLflow. El
de Q-learning es `qlearning-modelo-qlearning-v8-s1`.

**¿Por qué la semilla 1 y no la 0 o la 2?**
Por los criterios fijados antes: primero vueltas, después tiempo. La 1 tuvo 100 % en extremos; la 2, 99.8 %; la 0,
98.5 %. La diferencia con la 2 está dentro del ruido y lo decimos.

**¿El 100 % no será suerte de las semillas de evaluación?**
Por eso existe el test reservado, con semillas fuera del repositorio y una sola corrida: dio 100 % / 100 % y 99.9 %.

**¿Por qué PPO es mejor que Q-learning?**
La red trabaja con números continuos; la tabla agrupa situaciones en celdas y pierde detalle. Con 3 % de ruido en
los sensores, la tabla salta de celda y se confunde. Además PPO es 12 s más rápido en seco y 18 s con lluvia.

**¿Qué es DAgger y por qué lo usamos?**
Imitación con correcciones: la red maneja, comete errores y el maestro le dice qué hacer en cada situación nueva.
Copiar solo vueltas perfectas (v3) no sirvió, porque la red nunca veía cómo recuperarse de un error.

**¿Por qué el agente no ve el agarre?**
Porque ese es el incidente: un piloto real no sabe el coeficiente de fricción del asfalto. Solo ve si llueve y lo
que miden sus llantas.

**¿Por qué hay tantas versiones rechazadas?**
Porque el enunciado valora el proceso. Los fallos se conservan con su hipótesis y su decisión: muestran qué se
probó y por qué se descartó.

**¿Dónde están los pesos de los modelos?**
En DVC: `models/` para la versión del pipeline y `finalistas/` para las semillas 1 y 2. Se bajan con `dvc pull`. El
manifiesto de cada versión dice dónde están y su SHA-256.

**No me funciona `dvc pull`.**
Pide usuario y token de DagsHub (sección 8.2 y la guía). Si tu cuenta no puede leer el repositorio, pídele a Kevin
que te agregue.

**¿Puedo cambiar el ambiente o los pilotos?**
Sí, en una rama. Pero si cambias `env.py`, `policies.py` o `pipeline.py`, `dvc repro` puede querer reentrenar PPO,
que tarda horas. Revisa `dvc status` antes.

**¿Cómo hago un experimento nuevo?**
Escribe la `hipotesis` en `params.yaml` antes de entrenar, cambia el parámetro, corre `dvc repro`, compara en MLflow
y haz commit de `params.yaml` y `dvc.lock`. Luego `dvc push`, `rally sincronizar` y `rally manifiesto`.

**¿Cómo veo la web con simulación en vivo?**
Enciende la API (`rally api`) y la web (`npm run dev` en `web/`), y abre http://localhost:5173.

**¿Por qué la web pública dice "replay"?**
Desde el 6 de noviembre no debería: la API corre como función de Vercel en la misma URL. Si sale replay, la función
no respondió y la nota del panel dice por qué. Recarga; la primera carrera tras un rato sin uso tarda unos segundos.

**¿Qué es el "EXPERIMENTO #28" de la telemetría?**
Un contador de vueltas simuladas por la API desde que se encendió; vuelve a 1 si se reinicia. El modelo es el de la
etiqueta de arriba (por ejemplo `ppo-modelo-v5-s1`), y su run de MLflow está en el manifiesto.

**¿Por qué la web sale de un fork?**
Vercel no tenía acceso al repositorio de Miguel. El fork de Kevin tiene el mismo código.

**¿Qué pasa si un modelo nuevo sale peor?**
No pasa los criterios y no se promueve. Si ya se promovió, el rollback vuelve al anterior y queda anotado en
`historial.json`.

**¿Qué es un manifiesto y para qué sirve?**
La cédula de un modelo: de qué código salió, con qué ambiente, dónde están sus pesos, cómo comprobar que son esos y
qué resultados dio. Con él cualquiera puede recuperar y evaluar esa versión.

**¿Cómo se comprueba que el pipeline es reproducible?**
Se corrió el flujo completo desde cero en una copia aparte y dio exactamente los mismos resultados.

**¿Qué hago si el computador se recalienta?**
Usa menos núcleos con `taskset -c 0-3` y `nice -n 10`. El entrenamiento se reanuda desde su punto de guardado.

**¿Quién usó asistentes de código?**
Usamos asistentes de código y verificamos lo generado con pruebas y métricas. Lo dice el informe; cada integrante
debe poder explicar lo que se hizo.

---

## 17. Preguntas probables del docente

| Pregunta | Respuesta corta | Dónde mostrarlo |
|---|---|---|
| ¿Cómo recupero el modelo v1? | Su manifiesto da la etiqueta, el commit y el SHA-256; corre con adaptador | `manifests/ppo-modelo-v1.json`, catálogo de la web |
| ¿Con qué ambiente se entrenó cada modelo? | Campo `environment_version` del manifiesto | Catálogo |
| ¿Cómo sé que el peso es el correcto? | Se compara su SHA-256 con el del manifiesto | `model_sha256` |
| ¿Cuándo fijaron los criterios? | El 1 de noviembre, antes de ver los resultados 0.4 | Comentario en `configs/seleccion.yaml` |
| ¿Cómo evitan sobreajustar a la evaluación? | Semillas de entrenamiento distintas, pruebas extremas, tres semillas y test reservado de una sola corrida | `metrics/test-final.json` |
| ¿Qué fue lo más difícil? | La lluvia extrema; la causa era física, no de aprendizaje | Sección 6.1 |
| ¿Qué pasa si falla en producción? | Monitoreo en la API, criterios y rollback | `/api/monitoreo`, `historial.json` |
| ¿Cuál es la principal limitación? | Un solo circuito | Sección 15 |
| ¿Por qué Prefect? | Es Python, corre local sin servidor y deja evidencia por etapa | `pipelines/flujo.py` |
| ¿Qué harían después? | Pistas aleatorias y una pista reservada | Informe, última sección |

---

## 18. Glosario

| Término | Qué significa aquí |
|---|---|
| μ (mu) | Adherencia del asfalto: 0.9 seco, 0.5 mojado, 0.4 diluvio |
| Checkpoint | Puerta que el carro debe cruzar en orden |
| Episodio | Un intento de vuelta, de la salida hasta que termina |
| Semilla | Número que fija el azar: misma semilla, mismo arranque |
| PPO | Proximal Policy Optimization: algoritmo de refuerzo con red neuronal |
| Q-learning | Algoritmo de refuerzo con tabla de valores por situación y acción |
| DAgger | Imitación en la que el maestro corrige los errores del alumno |
| Dominio aleatorio | Sortear condiciones en cada episodio para que el agente generalice |
| Pruebas extremas | Las 19 condiciones fuera de lo base: diluvio, ruido, pistas angostas y anchas, etc. |
| Test reservado | Evaluación final con semillas ocultas, corrida una vez |
| Manifiesto | Archivo con la identidad completa de una versión de modelo |
| Adaptador | Conversión de observaciones para que un modelo viejo corra en el ambiente nuevo |
| Rollback | Volver al modelo recomendado anterior |
| Replay | Modo de la web que muestra vueltas grabadas, sin API |
| DVC | Control de versiones para datos y modelos |
| MLflow | Registro de experimentos y modelos |
| DagsHub | Servicio en la nube que guarda el remoto de DVC y la copia de MLflow |
| Prefect | Orquestador de flujos en Python |
| FastAPI | Biblioteca de Python para la API |
| Vercel | Servicio donde están publicadas la web y la API (función de Python) |

---

## 19. Enlaces

| Qué | Enlace |
|---|---|
| Repositorio | https://github.com/melo11miguel/defiende-el-servidor |
| Web | https://autonomous-rally.vercel.app |
| Experimentos | https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments |
| Datos y modelos | https://dagshub.com/kevin-nieto-callejas/autonomous-rally |
| Modelo publicado (PPO v5 semilla 1) | https://huggingface.co/Kevinnieto0001/autonomous-rally-ppo |
| Ficha del ambiente | [ambiente-v0.1.md](ambiente-v0.1.md) |
| Informe | [entregas/informe.md](entregas/informe.md) |
| Presentación | [entregas/presentacion/](entregas/presentacion/) |
| Guía para empezar | [guias/empezar.md](guias/empezar.md) |
| Bitácora | [registro/bitacora.md](registro/bitacora.md) |
| Evidencia | [evidencia/](evidencia/) |

Los enlaces de DagsHub piden iniciar sesión, y `dvc pull` necesita usuario y token: ver la
[guía](guias/empezar.md).
