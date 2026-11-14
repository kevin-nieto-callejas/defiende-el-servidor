# Licencias de los recursos usados

El enunciado pide documentar la licencia de los recursos (assets) que usa la aplicación. El repositorio no guarda
ningún modelo 3D, textura, sonido ni fuente de terceros: el visor los descarga al abrirse y, si no hay internet,
usa colores planos.

## Recursos que carga el visor

| Recurso | Dónde se usa | Origen | Licencia |
|---|---|---|---|
| Texturas fotográficas: `asphalt_track`, `cobblestone_01`, `brick_pavement_02`, `clay_roof_tiles`, `grey_plaster`, `grey_plaster_02`, `leafy_grass` | Asfalto, pianos, calles, edificios y pasto ([escenario.js](../src/rally/static/escenario.js), [texturas.js](../src/rally/static/texturas.js)) | [Poly Haven](https://polyhaven.com) | CC0 (dominio público) |
| Cielos HDR: `belfast_sunset_puresky`, `kloofendal_overcast_puresky` | Iluminación en seco y con lluvia | Poly Haven | CC0 |
| Modelo 3D `street_lamp_01` (autor: Josh Dean) | Faroles | Poly Haven | CC0 |
| Modelo 3D `ferrari.glb`, "Ferrari 458 Italia" de [vicent091036](https://sketchfab.com/models/57bf6cc56931426e87494f554df1dab6) | Carrocería del carro, con pintura y calcomanías propias | Ejemplos de three.js r170 (`examples/models/gltf/`) | Atribución al autor, como hace el ejemplo `webgl_materials_car` de three.js. No pudimos confirmar su licencia exacta en Sketchfab |
| Textura `waternormals.jpg` | Agua del puerto | Ejemplos de three.js r170 | Distribuida con three.js (MIT) |
| Fuentes Titillium Web y JetBrains Mono | Interfaz del visor | Google Fonts | SIL Open Font License 1.1 |
| Fuentes Oswald y Public Sans | Presentación | Google Fonts | SIL Open Font License 1.1 |

## Recursos propios

- **Moto MotoGP, piloto, pista, graderías, túnel y calcomanías:** geometría y texturas generadas en código
  ([moto.js](../src/rally/static/moto.js), [carro.js](../src/rally/static/carro.js),
  [escenario.js](../src/rally/static/escenario.js)).
- **Sonido:** se sintetiza en el navegador con Web Audio API ([sonido.js](../src/rally/static/sonido.js)); no
  hay archivos de audio.
- **Circuito:** trazado propio "inspirado en Mónaco". No usa datos, logotipos ni marcas del circuito real.

## Bibliotecas

| Biblioteca | Versión | Licencia |
|---|---|---|
| three.js | 0.170.0 | MIT |
| Vite / TypeScript | 6.4 / 5.9 | MIT / Apache 2.0 |
| Gymnasium | 1.4.0 | MIT |
| Stable-Baselines3 | 2.9.2 | MIT |
| PyTorch | 2.15.0 (CPU) | BSD-3 |
| NumPy / SciPy | 2.5.4 / 1.18.1 | BSD-3 |
| MLflow | 3.17.2 | Apache 2.0 |
| DVC | 3.67.1 | Apache 2.0 |
| FastAPI / Uvicorn | 0.162.0 / 0.54.0 | MIT / BSD-3 |
| Prefect | 3.9.1 (entorno aparte, `~/.venvs/rally-flujo`) | Apache 2.0 |

Las versiones exactas de Python están en [requirements.txt](../requirements.txt), y las del frontend en
[web/package-lock.json](../web/package-lock.json).
