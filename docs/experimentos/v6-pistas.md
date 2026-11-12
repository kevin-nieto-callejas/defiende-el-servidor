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
Por eso `presupuesto.segundos` del manifiesto (5 646 s) cuenta solo la parte reanudada; DAgger y los primeros
400 000 pasos de PPO tomaron unas 3.5 horas más, con pausas por la suspensión del Mac.

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

## Fase B: Sierra (`metrics/sierra-v6.json`)

Corrida una sola vez, el 8 de noviembre de 2026 a las 03:01, sobre el commit de la elección (`bc081e8`), con
100 semillas en seco y con lluvia.

| Piloto | Seco | Lluvia | Dónde falla |
|---|---|---|---|
| Experto (asume piso seco) | 100 % · 74.8 s | 0 % | con lluvia, antes del Mirador Alto |
| Maestro | 100 % · 78.0 s | 100 % · 99.8 s | |
| v5, semilla 1 (la recomendada hoy) | **0 %** | **0 %** | antes de la salida del Paso, en las 200 vueltas |
| Control, solo Mónaco | 100 % · 77.3 s | 100 % · 99.4 s | |
| **v6, tres pistas** | **100 % · 68.8 s** | **100 % · 88.0 s** | |

## Conclusión

**La hipótesis se cumple.** La v6 completa el 100 % de las vueltas en la Sierra, que ningún modelo vio al
entrenar (pedíamos al menos 80 %), y en Mónaco no pierde frente al control: completa lo mismo y es más rápida.

La lectura completa es más fina que "entrenar en más pistas generaliza":

1. **La v5-s1 sí memorizó Mónaco.** Da 100 % en Mónaco y 0 % en el Puerto y en la Sierra, aunque el maestro
   completa las dos. El modelo que hoy publica el proyecto no sabe manejar fuera de su pista.
2. **El control, solo Mónaco, también completa la Sierra.** Terminar la vuelta no exige practicar en varias
   pistas; lo que se pierde es velocidad: el control es el más lento de los modelos entrenados que completan.
3. **Lo que aportan las tres pistas es poder afinar sin memorizar.** La v6 siguió mejorando con PPO hasta el
   final (su mejor punto es el paso 3 000 000) y es 11 % más rápida que el control en la Sierra (68.8 contra
   77.3 s en seco, 88.0 contra 99.4 s con lluvia), sin perder vueltas en ninguna pista.

## Selección oficial: la v6 no se promueve (10 de noviembre)

Kevin corrió el protocolo oficial con la v6 en `models/ppo` (`dvc repro -s evaluar` y `-s generalizacion`, en
Linux) y después `rally seleccionar`. En la ficha dio 100 % en seco (69.8 s) y 100 % con lluvia, igual que en el
Mac. Pero en las 19 pruebas extremas promedió **79.2 %** (mínimo 85 %), y su peor prueba, diluvio, dio **0 %**
(mínimo 50 %); también cayó en límite de lluvia (14 %), pista angosta en seco (5 %) y sensores cortos con lluvia
(0 %). No pasa la selección, y el recomendado sigue siendo `ppo-modelo-v5-s1`.

Eso abrió una pregunta: ¿la v6 cae en los extremos por practicar en tres pistas, por haberse entrenado en el Mac
o por su semilla?

## Segunda semilla y pruebas extremas (`metrics/semillas-v6.json`, `metrics/generalizacion-v6-control.json`)

Entrenamos la v6 y el control con la **semilla 1** en GitHub Actions (`.github/workflows/semillas-v6.yml`, run
`42948616971`, Ubuntu con el `requirements.txt` del proyecto), con la misma configuración. Los modelos están en
DVC (`models/semillas-v6.dvc`; v6-s1 `1f68d191…`, control-s1 `9c00b8b1…`) y las corridas, en MLflow de
DagsHub (`ppo-v6-s1` y `ppo-control-s1`). Los evaluamos en las pistas de la fase A, **sin la Sierra**, que ya
se usó una vez, y corrimos las 21 pruebas de `rally seleccionar` con los cuatro modelos
(`scripts/analisis/generalizacion_modelos.py`, mismas semillas y mismo ruido que la etapa `generalizacion`; con
la v6 semilla 0 da 78.9 %, cerca del 79.2 % de Kevin en Linux).

**Fase A, semilla 1** (vueltas en 100 semillas, seco / lluvia):

| Modelo | Mónaco | Bosque | Puerto | Puerto r9.5 |
|---|---|---|---|---|
| v6, semilla 1 | 100 / 100 · 80.4 / 104.8 s | 100 / 100 | 100 / 100 | 100 / 100 |
| Control, semilla 1 | 100 / 100 · 81.5 / 104.7 s | **0 / 0** | 100 / **0** | 100 / **0** |

**Pruebas extremas** (promedio de las 19 calificadas y peor prueba):

| Modelo | Dónde se entrenó | Mejor punto del entrenamiento | Promedio | Peor prueba |
|---|---|---|---|---|
| v6, semilla 0 | Mac | paso 3 000 000 | **78.9 %** | diluvio, 0 % |
| v6, semilla 1 | GitHub Actions | paso 200 004 | **100 %** | ninguna por debajo de 100 % |
| Control, semilla 0 | Mac | paso 400 008 | 98.0 % | sensores largos con lluvia, 62 % |
| Control, semilla 1 | GitHub Actions | paso 0 | 94.7 % | sensores cortos con lluvia, 0 % |

Lo que enseña:

1. **Practicar en tres pistas da un resultado estable; practicar solo en Mónaco, no.** Las dos semillas de la v6
   completan las cuatro pistas de la fase A en seco y con lluvia. El control cambia mucho de una semilla a otra:
   la semilla 0 completa el Puerto y choca con lluvia en el Bosque (30 %); la semilla 1 no termina nunca el
   Bosque y no completa el Puerto con lluvia. Que el control semilla 0 completara la Sierra fue, en parte,
   suerte de la semilla.
2. **La caída de la v6 en los extremos no se debe a las tres pistas ni al Mac.** La v6 semilla 1 aguanta las 19
   pruebas al 100 %, y el control semilla 0, entrenado en el mismo Mac que la v6 semilla 0, promedia 98 %.
3. **Lo que distingue a la v6 semilla 0 es cuánto afinó con PPO.** Es la única cuyo mejor punto fue el final
   (paso 3 000 000); en los otros tres, el mejor punto quedó cerca de la red recién imitada del maestro (paso
   400 008 o antes). También es la más rápida (69.8 s en Mónaco, contra 79.6 a 81.5 s de los otros tres). Nuestra hipótesis es que
   afinar mucho con PPO cambia robustez en condiciones extremas por velocidad. Con dos semillas no lo podemos
   separar del azar de la semilla, y no lo comprobamos.
4. **La v6 semilla 1 cumpliría los criterios de `configs/seleccion.yaml`** según estas mediciones: 100 % en seco
   y con lluvia, 80.4 s en seco (máximo 81.3 s), 100 % en extremos (mínimo 85 %) y peor prueba 100 % (mínimo
   50 %). La decisión sigue siendo del flujo oficial de selección, que debe correrla con su propio protocolo.
   Ojo: la v6 semilla 1 **no tiene prueba en una pista que nunca vio**. Para ella, el Bosque y el Puerto son de
   entrenamiento, y la Sierra ya se usó; su capacidad de manejar pistas nuevas se apoya en el resultado de la
   semilla 0 en la Sierra y en que la misma configuración se comporta igual en las dos semillas.

## Veredicto de selección de la v6 semilla 1 (12 de noviembre)

Aplicamos `seleccion.decidir`, la función de `rally seleccionar`, con los criterios de `configs/seleccion.yaml`
(fijados el 1 de noviembre) y contra el recomendado actual, `ppo-modelo-v5-s1`. Los insumos son las mediciones
de Linux de las secciones anteriores: la ficha en Mónaco (semillas 0 a 99) y las 21 pruebas extremas, con la
red exportada a numpy (diferencia con PyTorch menor a 1e-6). Los veredictos quedaron en
`manifests/decisiones.json` con `seleccion.anotar`. **No se promovió nada.**

| Candidato | Seco | Lluvia | Tiempo seco | Extremos | Peor prueba | Veredicto |
|---|---|---|---|---|---|---|
| `ppo-modelo-v6-pistas-s1` | 100 % | 100 % | 80.4 s (máx. 81.3) | 100 % (mín. 85) | 100 % (mín. 50) | **aceptado**, 7 de 7 criterios |
| `ppo-control-monaco-s1` | 100 % | 100 % | 81.5 s | 94.7 % | sensores cortos con lluvia, 0 % | rechazado |

La v6 semilla 1 es el primer modelo que **maneja en pistas nuevas y aguanta las condiciones extremas** a la vez.
Para promoverla falta lo que solo puede hacer quien tiene el entorno de despliegue:

1. Correr el test reservado (`rally test-final`), una sola vez, como se hizo con la v5-s1. Su semilla está solo
   en el `.env` de Kevin.
2. Registrarla en el catálogo (manifiesto y etiqueta) y agregar su red numpy al paquete de Vercel. La exportación
   ya existe en `models/semillas-v6/v6-s1/modelo.npz`, hecha en Linux.
3. Si pasa, promoverla con `rally seleccionar --promover` o con el flujo de Prefect, publicar Vercel desde el
   fork y abrir el pull request en Hugging Face.

Límite que hay que decir: la v6 semilla 1 no tiene prueba en una pista que nunca vio (ver el punto 4 de la
sección anterior).

### Test reservado de la v6 semilla 1: regla fijada antes de correrlo (12 de noviembre)

La semilla del test de la v5-s1 está solo en el `.env` de Kevin, así que para la v6 semilla 1 usamos una semilla
nueva: se generó al azar, se guardó en el `.env` de Miguel sin mostrarse y nadie la vio antes del test. Se
publica solo su SHA-256. El test corre una vez (`scripts/analisis/test_final_npz.py`, mismo procedimiento que
`rally test-final`: 100 semillas, seco, lluvia y las 19 pruebas extremas) con la red en numpy, en el Mac.

**Regla, escrita antes de ver el resultado:** el test reservado debe cumplir los mismos umbrales de
`configs/seleccion.yaml` (seco y lluvia de al menos 98 %, tiempo en seco de 81.3 s o menos, promedio de extremos
de al menos 85 % y ninguna prueba por debajo de 50 %). Si los cumple, la v6 semilla 1 se promueve a recomendada;
si no, queda como candidata y el recomendado sigue siendo `ppo-modelo-v5-s1`.

## Test reservado y promoción de la v6 semilla 1 (12 de noviembre)

El test corrió una sola vez, con 100 semillas secretas (SHA-256 `541487e6…`) y la red en numpy en el Mac:

| Seco | Lluvia | Pruebas extremas | Peor prueba |
|---|---|---|---|
| 100 % · 80.4 s | 100 % · 104.8 s | 100 % (19 de 19 en 100 %) | 100 % |

Cumple los cinco umbrales de la regla fijada en `5ed48de`, así que **la v6 semilla 1 se promovió a recomendada**
con `seleccion.promover`. Quedó como la entrada más reciente de `manifests/historial.json`; el rollback a la v5-s1
sigue disponible con `rally seleccionar --rollback "motivo"`. Su manifiesto pasa a `aceptado` y guarda el resumen
del test. El test corrió en el Mac, mientras que la v5-s1 tuvo el suyo en Linux; las diferencias de plataforma que
medimos fueron de 2 a 4 puntos en pruebas límite, y aquí ninguna prueba bajó de 100 %. Los 16 769 segundos que
registra el archivo incluyen horas en que el Mac estuvo suspendido por batería.

## Errores que aceptamos y límites

- **Dos semillas por modelo.** La segunda semilla confirmó que la v6 es estable en las pistas de la fase A y que
  el control no lo es, pero con dos semillas no podemos separar el efecto de afinar con PPO del azar de la
  semilla. La semilla 1 se entrenó en Linux (GitHub Actions) y la semilla 0 en el Mac.
- **Cuatro pistas, todas del mismo generador.** Rectas y arcos de radio constante, con escape y muro igual de
  anchos; la Sierra es nueva pero de la misma familia. No probamos curvas de radio variable, pendientes ni
  pistas mucho más largas.
- **La regla de elección no miró las pruebas extremas** (ruido, ancho, alcance de sensores) de la ficha, y por
  eso la v6 semilla 0 ganó la fase A y después no pasó la selección oficial. Una próxima regla de elección debería
  incluir las pruebas extremas desde el principio.
- **Plataforma.** El control y la v6 se entrenaron en macOS (Intel) con PyTorch 2.2.2 y numpy 1.26; las v5,
  en WSL con PyTorch 2.15. La huella del ambiente cambia entre plataformas (`d56c0fcd9d9d` en macOS,
  `61fa0dd41b7c` en Linux) porque la geometría difiere en el último bit; las demostraciones del experto dan
  las mismas 20 904 acciones en las dos (observaciones con diferencia menor a 1e-11).
