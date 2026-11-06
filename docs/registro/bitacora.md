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

## 5 de noviembre

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
