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
- Un clon limpio mostró que `dvc pull` pide credenciales y que la web de DagsHub pide iniciar sesión, aunque el
  repositorio no es privado. Se corrigió la documentación, que decía lo contrario.
