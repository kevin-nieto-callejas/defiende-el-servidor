# Bitácora del proyecto

Registro cronológico de decisiones, fallos y correcciones. Los commits de git tienen el detalle.

## 23 de octubre

- Miguel crea el repositorio para el proyecto *Defiende el servidor*.
- El curso entrega las fichas de ambientes. Al equipo le corresponde Autonomous Rally.

## 28 de octubre

- Ficha del ambiente y circuito de Mónaco de 1 048.6 m.
- `modelo-v1`: 100 % en seco y 0 % con lluvia.

## 29 de octubre

- `modelo-v2`: el sensor de agarre no resolvió la lluvia. En seco bajó a 63.1 s, pero con lluvia chocaba antes.
- `experimento-v3`: rechazado, 0 % en ambos pisos. Copiar vueltas perfectas no sirve: al primer error la red llega
  a estados que nunca vio.
- `modelo-v4`: DAgger con piloto maestro. 100 % en seco y con lluvia.
- Prueba de generalización: la v4 aguanta 6 de 7 pruebas; ruido con lluvia, 63 %.

## 30 de octubre

- Visor 3D estilo transmisión.
- Q-learning con DAgger tabular: 60 % en seco y 15 % con lluvia.

## 1 de noviembre

### Revisión contra el enunciado

- Se encontraron requisitos sin cubrir: Vercel, manifiestos, orquestador, rollback, 3 semillas y test reservado.
- Se cambió la prioridad: primero lo que pesa en la rúbrica y después los gráficos.

### El 100 % engañoso

- El equipo reportó choques en los experimentos del visor.
- Medición en 35 combinaciones: la v4 dio 0 % en 11. Causa: rayos divididos por el alcance y carro desconocido.
- Con μ 0.4 ningún piloto completaba la vuelta. Causa física: el pedal gastaba todo el agarre.

### Ambiente 0.4 y modelos nuevos

- Observación de 24 valores, rayos con escala fija, nota de velocidad segura y control de tracción en el maestro.
- Criterios de selección escritos antes de ver resultados, en `configs/seleccion.yaml`.
- Q-learning v7: 87 % / 81 %. Q-learning v8: 99 % / 100 %. En la v8 el aprendizaje por refuerzo sí mejoró la imitación.
- PPO v5: 100 % / 100 %.

### Infraestructura

- API con FastAPI, web con Vite y TypeScript, manifiestos con SHA-256 y adaptadores para modelos viejos.
- Flujo de Prefect probado sin entrenar, y rollback v5 → v4 → v5 comprobado contra la API.
- Web publicada en Vercel en modo replay, desde un fork, porque Vercel no tiene acceso al repositorio de Miguel.
- DagsHub dio errores 502: se separó la subida de la cola para no frenar el entrenamiento, y luego funcionó.
- `modelo-v1` tenía 4 archivos sin subir a DagsHub, porque `dvc push` lo saltaba. Se subieron directamente.

### Apagón por calor

- A las 19:50 el computador se apagó de forma inesperada con 12 núcleos trabajando.
- Sin daños. Se perdió el avance de PPO semilla 2, que reinició desde cero.
- Se bajó a 7 núcleos y se desactivó el Turbo. No volvió a ocurrir.

### Selección final

- PPO, extremos: semilla 0, 98.5 %; semilla 1, 100 %; semilla 2, 99.8 %.
- Se eligieron las semillas 1 de cada agente antes de correr el test reservado.
- Test reservado: PPO 100 % / 100 % y 99.9 %; Q-learning 99 % / 99 % y 84.8 %.

### Correcciones de la revisión de la web

- En replay, mover un deslizador recargaba la vuelta base sin avisar. Ahora responde que necesita la API.
- El aviso tapaba los instrumentos y la nota del panel decía algo falso en replay. Se corrigieron.
- En celular los paneles tapaban la pista. Ahora empieza con el panel plegado.

### Cierre

- Se unió la rama `mejoras-kevin` (gráficos) a `main`, después de medir rendimiento: 31 FPS en Media, igual que
  antes, y 27 contra 31 con lluvia. En calidad Alta baja a 11 FPS.
- Mediciones hechas con el Turbo apagado y en un navegador sin ventana.
- Al recargar se veían el carro básico y el escenario incompleto durante unos segundos. La pantalla de carga ahora
  espera texturas, cielo, carro y shaders. La vuelta y la medición de FPS arrancan cuando todo está listo.
- Un clon limpio mostró que `dvc pull` pide credenciales y que la web de DagsHub pide iniciar sesión, aunque el
  repositorio no es privado. Se corrigió la documentación, que decía lo contrario.

## 2 de noviembre

- Flujo completo de Prefect con entrenamiento real, en una copia aparte. Reprodujo los resultados oficiales sin
  ninguna diferencia, aunque el computador se suspendió siete horas a mitad de PPO por batería baja.

## 3 de noviembre

- Resumen general ampliado para el equipo.
- Hugging Face pasa de PPO v4 a `ppo-modelo-v5-s1`, con la etiqueta `v5-s1`, el manifiesto y el test reservado. El
  SHA-256 del modelo bajado de Hugging Face coincide con el del manifiesto. `rally publicar` no sirvió porque sube
  `models/ppo`, que es la semilla 0.
- Intento de publicar la API en un Hugging Face Space: el paquete se armó y verificó, pero Hugging Face rechazó
  crear el Space porque los Spaces con Docker ya exigen la suscripción PRO. No se creó nada. Se decide con el docente.
- Probando la web en vivo con todos los deslizadores al extremo, PPO v5 semilla 1 se salió. Con 3 semillas por
  combinación: diluvio solo, 3 de 3; diluvio con pista de 6 m o sensores de 10 m, 3 de 3; diluvio con aceleración
  6, 1 de 3; todo al extremo, 0 de 3. Las pruebas extremas nunca combinaron condiciones. Queda como límite.

## 6 de noviembre

- Los compañeros veían "necesita la API" al pasar a lluvia en la web pública. No era un fallo de la lluvia: en replay
  solo hay vueltas con la semilla 0 y los valores base, y cualquier deslizador o semilla distinta pide la API.
- Se unió la rama `api-vercel` de Allison a `main` con el paquete de modelos reales (2.8 MB, sin tokens ni la
  semilla reservada). El primer build en Vercel falló con `unused_function`: Vercel busca la función leyendo
  `index.py` y no reconoce un `app` definido dentro de un `if`. Se reprodujo con `vercel build` 65.11.0 en local y
  se corrigió dejando `app` al nivel del módulo. La función pesa 191 MB, bajo el límite de 500.
- API publicada en https://autonomous-rally.vercel.app. Probada desde la URL: seco y lluvia con PPO v5-s1 y
  Q-learning v8-s1, pista de 10 m con semilla 7, y evaluar 10 vueltas con lluvia en 8.4 s. Ya no sale el aviso de
  replay.
- Allison y Miguel quedan como colaboradores de DagsHub con permiso Write, invitados por correo. Ya pueden hacer
  `dvc pull` y rearmar el paquete de la API con los modelos reales.

## Del 6 al 8 de noviembre: experimento v6 (Miguel, rama `1Experiment`)

- Pregunta: ¿el PPO aprendió a manejar o memorizó Mónaco? Agregamos tres pistas: Bosque (rápida, sentido
  horario), Puerto (técnica) y Sierra (reservada para la prueba; el código no deja entrenar con ella).
  Mónaco quedó idéntica: comparamos la geometría, los rayos y los choques con la versión anterior en 5 000
  puntos al azar.
- La v5-s1 da 100 % en Mónaco y **0 %** en el Puerto, donde el maestro da 100 %. Con el Puerto abierto a curvas
  de 9.5 m sigue en 0 %: no es solo que las curvas sean más cerradas que las de Mónaco.
- Entrenamos en el Mac de Miguel la v6 (Mónaco, Bosque y Puerto) y un control solo con Mónaco, con la misma
  configuración y la misma semilla. Escribimos la regla de elección y el uso único de la Sierra antes de ver
  resultados (commit `941798f`).
- El Mac se suspendió al cerrar la tapa con batería y después se apagó. La v6 siguió desde el punto de
  guardado del paso 400 008; el run interrumpido quedó como `KILLED` en MLflow.
- Fase A: la v6 completa 100 % en Mónaco, Bosque y Puerto, en seco y con lluvia, y es más rápida que el
  control. Elegida la v6 (commit `bc081e8`).
- Sierra, una sola vez: v6 100 % (68.8 s / 88.0 s), control 100 % (77.3 s / 99.4 s), v5-s1 0 %. La hipótesis se
  cumple; el control también completa, así que lo que aportan las tres pistas es poder afinar con PPO sin
  memorizar. Detalle, tablas y límites en [experimentos/v6-pistas.md](../experimentos/v6-pistas.md).
- La huella del ambiente cambia entre Linux y macOS (`61fa0dd41b7c` frente a `d56c0fcd9d9d`) con el mismo
  código: la geometría difiere en el último bit. Las demostraciones del experto dan las mismas 20 904 acciones
  en las dos plataformas. El manifiesto de la v6 dice en qué máquina se entrenó.

## 10 de noviembre: Q-learning sin reentrenar

- Al unir el experimento v6, DVC marcó la etapa `qlearning` como desactualizada: cambiaron `demos.npz` (se
  regeneró en el Mac) y cuatro archivos de código (`env.py`, `track.py`, `pipeline.py`, `qlearning.py`). El
  flujo de selección habría corrido `dvc repro` y reentrenado Q-learning por horas.
- Comprobamos que ninguno de los dos cambios altera el modelo. `agentes/qlearning.py` no lee `demos.npz` (la
  etapa solo lo registra en MLflow), y las demostraciones del Mac tienen las mismas 20 904 acciones que las de
  Linux. Para el código, entrenamos Q-learning recortado (2 iteraciones de DAgger y 30 episodios) con el código
  anterior al experimento (`b4e00f2`) y con el actual, en la misma máquina: la tabla Q y las visitas salieron
  idénticas byte a byte (`scripts/analisis/comparar_qlearning.py`).
- Con esa evidencia registramos la etapa con `dvc commit qlearning`, sin reentrenar: en `dvc.lock` cambian solo
  los hashes de las dependencias, y la salida `models/qlearning` sigue siendo `993f3455…`.

- La API se publica como función de Vercel, en el mismo dominio de la web: es gratis y cumple lo que pide el
  enunciado sin contratar un servicio. PyTorch no cabe en una función, así que la red de PPO se exporta a numpy
  (`src/rally/agentes/red_numpy.py`). Antes de guardar cada red se comparan sus acciones con las de PyTorch en
  unas 7 000 observaciones; con modelos de prueba la diferencia máxima fue 9e-8.
- `deploy/api/empaquetar.py --vercel` arma `web/api/_paquete` y `--verificar` comprueba que coincida con `src/`
  y `manifests/`. Una prueba lo revisa en cada `pytest`.
- La web ya no decide el modo por una variable: pregunta a `/api/salud` y, si no responde, entra en replay con el
  motivo en pantalla. Probado en un navegador sin ventana con la API arriba (catálogo, evaluación con adaptador)
  y con la API caída (replay con "la API respondió 500").
- GitHub Actions corre pruebas, compila la web, revisa el paquete y construye el contenedor en cada push. Aquí no
  se pudo construir la imagen porque el registro de Docker estaba bloqueado en el entorno de trabajo.
- Las tablas Q anteriores a la v6 ahora responden 409 en la API (antes, 503 por pesos no encontrados).

## 12 de noviembre: la v6 semilla 1 pasa la selección y el test reservado, y se promueve (Miguel)

- Con `seleccion.decidir` y `configs/seleccion.yaml`, la v6 semilla 1 cumple los 7 criterios; anotado en
  `decisiones.json`. Se registró en el catálogo como candidata, con etiqueta `modelo-v6-pistas-s1` y su red numpy en
  el paquete de la API.
- Test reservado con una semilla nueva (en el `.env` de Miguel; no se pudo crear como secreto de GitHub desde la
  sesión): 100 % en seco, 100 % con lluvia y 100 % en las 19 pruebas extremas. Regla fijada antes (`5ed48de`).
- Promovida con `seleccion.promover`. Es el primer modelo que maneja pistas nuevas y aguanta las condiciones
  extremas. Falta publicarla en Vercel desde el fork y en Hugging Face.

## 11 y 12 de noviembre: segunda semilla en GitHub Actions (Miguel)

- Entrenamos la v6 y el control con la semilla 1 en GitHub Actions (`.github/workflows/semillas-v6.yml`), para
  no depender de la batería ni del calor del Mac. Allá DAgger tardó de 9 a 20 minutos (en el Mac, unas 3.5 horas)
  y cada modelo terminó en poco más de una hora. Un primer intento con "ensayo corto" corrió completo porque la
  condición no se aplicó; lo cancelamos y quitamos ese modo.
- Fase A con la semilla 1: la v6 completa Mónaco, Bosque, Puerto y Puerto r9.5 en seco y con lluvia, igual que la
  semilla 0. El control no: 0 % en el Bosque y 0 % con lluvia en el Puerto. Practicar en tres pistas da un
  resultado estable entre semillas; practicar solo en Mónaco, no.
- Las 21 pruebas extremas con los cuatro modelos: v6-s0 78.9 % (diluvio 0 %), v6-s1 **100 %**, control-s0 98.0 %,
  control-s1 94.7 % (sensores cortos con lluvia 0 %). La caída de la v6-s0 no viene de las tres pistas ni del Mac;
  lo que la distingue es que es la única que afinó con PPO hasta el final (y la más rápida).
- La v6-s1 cumpliría `configs/seleccion.yaml` según estas mediciones (80.4 s en seco, máximo 81.3 s). Queda para
  el flujo oficial. No tiene prueba en una pista nueva: la Sierra ya se usó.
- Modelos en DVC (`models/semillas-v6.dvc`, subidos a DagsHub) y corridas copiadas a MLflow de DagsHub. Detalle en
  [experimentos/v6-pistas.md](../experimentos/v6-pistas.md).

## 10 de noviembre

- Se unió el PR #3 de Miguel: selector de pista en la web y la API (Mónaco, Bosque y Puerto; la Sierra responde
  403). Revisado antes de unir: 85 pruebas, build de la web, paquete de Vercel al día y la demo del Puerto con los
  pesos del paquete (v5-s1 se sale en seco y choca con lluvia; v6 completa en 78.8 s y 99.6 s).
- Evaluación oficial de la v6 (`dvc repro -s evaluar` y `-s generalizacion`). Ficha: 100 % en seco (69.8 s, la
  más rápida) y 100 % con lluvia. Generalización: promedio 79.2 % y diluvio 0 %, debajo de los mínimos de
  `configs/seleccion.yaml` (85 % y 50 %). También cae en límite de lluvia (14 %), pista angosta en seco (5 %) y
  sensores cortos con lluvia (0 %), donde la v5 daba 100 %. **`rally seleccionar` la rechaza** y el recomendado
  sigue siendo `ppo-modelo-v5-s1`. La v6 generaliza a pistas nuevas pero pierde robustez en condiciones extremas
  de Mónaco; los criterios se fijaron el 1 de noviembre, antes de ver estos resultados.
- No se corrió `pipelines/flujo.py` completo: su `dvc repro` habría reentrenado Q-learning, que quedó desactualizado
  porque el PR #2 cambió `demos.npz`, y habría promovido la v6 sola si pasaba. Q-learning sigue sin reentrenar.
- La generalización tardó 4 h 40 min sin terminar: cada proceso abría ~8 hilos de PyTorch para cálculos diminutos.
  Con `OMP_NUM_THREADS=1` y 10 procesos terminó en 25 min. Antes, el computador estuvo suspendido 8 horas porque
  se desconectó el cargador; la evaluación siguió sin perder nada al reanudar.
- Manifiestos: `normalization_uri` y `parent_run_id`, que pide el enunciado, estaban vacíos. Ahora
  `normalization_uri` apunta al código del ambiente, que es donde está la escala (no hay VecNormalize), y
  `parent_run_id` va vacío con una nota: ningún modelo hereda pesos; la v6 se reanudó desde el paso 400 008 de un
  run interrumpido cuyo id no quedó guardado. Una prueba revisa los 12 campos en todos los manifiestos.
- El generador creaba `qlearning-modelo-v6-pistas.json`, que era la tabla de Q-learning v8 con otro nombre (mismo
  SHA-256 y mismo run). Se excluyó.
- Cada veredicto de selección queda en `manifests/decisiones.json` (`rally seleccionar --anotar`). No va en
  `historial.json` porque el rollback vuelve a la entrada anterior del historial, que debe ser una promoción.
- Flujo de Prefect sin entrenar con la v6 de candidata: la rechazó sin intervención y la API siguió sirviendo la
  v5-s1 (evidencia en `docs/evidencia/flujo-rechazo-v6/`). El primer intento lo detuvo el propio flujo en las
  pruebas: el código había cambiado y el paquete de la API de Vercel no. Se rearmó y pasó.
- `dvc status` limpio sin reentrenar. Se volvieron a correr `datos`, `evaluar` y `generalizacion`: `demos.npz`
  salió con el mismo hash con que se entrenó Q-learning (la copia del Mac tenía los mismos datos con otros bytes) y
  las métricas, 11 500 vueltas, salieron idénticas a las publicadas. `qlearning` quedó registrada con la
  evidencia del PR #4 y `ppo` con `dvc commit`: el único cambio en `track.py` es el nombre para mostrar, que solo
  usa la web, y con DAgger el PPO no lee `demos.npz`.
- Al volver a correr `registrar`, el alias `@champion` de `rally-qlearning` pasó de la versión 9 (semilla 1, la
  elegida) a la 8 (semilla 0, la de `models/qlearning`). Se devolvió a la 9 y quedó anotado en el resumen.

## 13 nov 2026 — integración de la v6 semilla 1 y la moto, Hugging Face y sonido

- Los PR #8 (v6 semilla 1, Miguel) y #7 (moto, Allison) chocaban en 5 archivos. Se unieron en el PR #9: quedan los
  dos lados en `manifiesto.py`, el catálogo tiene 20 filas y el paquete de Vercel 16 modelos, sin reexportar ninguno.
- El #7 reorganizó `env.py`, `pipeline.py`, `policies.py` y los agentes, y DVC marcaba las 6 etapas del carro como
  modificadas. Se comprobó que el carro no cambia: misma huella física en 100 000 valores con acciones al azar, y
  `datos` y `evaluar` vueltos a correr dan los mismos números (solo agregan `vehiculo`). Luego `dvc commit` del
  resto, sin volver a correr `registrar` para no mover `@champion`.
- La tabla Q de la moto (`models/moto/qlearning`) no está en DagsHub: `dvc pull` falla. Falta su `dvc push`.
- Vercel en producción con el commit `c9906d2`: sirve la v6 semilla 1 y la moto; la v6-s1 completa el Puerto con
  lluvia en la función de Python, y pedir la moto en el carro responde 409.
- Hugging Face (`Kevinnieto0001/autonomous-rally-ppo`): la v6 semilla 1 con la etiqueta `v6-s1`, su manifiesto y su
  test reservado. El SHA-256 del archivo bajado coincide con el manifiesto. La etiqueta `v5-s1` sigue ahí para rollback.
- Sonido en el visor (`static/sonido.js`), sintetizado con Web Audio, sin archivos: motor con caja de cambios según
  la velocidad del episodio, chillido cuando el simulador marca derrape, grava, rocío con lluvia, viento, público
  que sube frente a las graderías, eco en el túnel, Doppler y paneo con la cámara de TV, cuenta regresiva (el carro
  espera en la salida), fanfarria y aplausos al completar la vuelta, golpe al chocar. Volumen por canal en 🔊, y M
  silencia. Medido en Chrome: sin excepciones, picos de 0.33 en carrera y 0.64 en la llegada, sin saturar.
- MLflow: el `@champion` de `rally-ppo` seguía en la v5-s1 (versión 6) aunque la recomendada era la v6-s1. Se
  registró la v6-s1 como versión 7: apunta a `models/semillas-v6/v6-s1`, con su SHA-256 verificado, y enlaza a su
  run en DagsHub, porque se entrenó en GitHub Actions. Quedan `@champion` = 7 y `@rollback` = 6.
- Presentación (18 diapositivas, dos nuevas: segunda semilla y moto), informe y resumen general actualizados a la v6-s1.
- Vercel publica en producción con un push a `main` del fork (`kevin`); `ambiente-v0.4` queda para vistas previas.

## 13 nov 2026 (noche) — moto MotoGP rediseñada

- Pedido de Kevin: una moto con calidad de MotoGP real, guiada por una foto de referencia y con los colores del
  proyecto (los del carro: azul, azul oscuro, dorado, amarillo, blanco y el 24).
- `static/moto.js` rehecho, sin modelos descargados: silueta de prototipo (nariz sobre la rueda y carenado que la
  rodea por detrás), decoración con cortes blancos angulares y franjas doradas, fibra de carbono, alerones con
  perfil de ala, cúpula ahumada, horquilla invertida dorada, discos perforados flotantes con pinzas radiales,
  basculante de aluminio, cadena y corona, resorte amarillo, escape de titanio, llantas slick con letras en el
  flanco y piloto con casco decorado y deslizadores en las rodillas.
- Las medidas del simulador no cambian (largo, ejes, radio de llanta): es solo dibujo. Probado en Chrome con lluvia,
  túnel, curva con inclinación y sonido: sin excepciones, ~30 FPS como antes.
