# Guía para empezar

Probado con Python 3.14 en WSL Ubuntu y Node 22.

## 1. Bajar el proyecto

```bash
git clone https://github.com/melo11miguel/defiende-el-servidor.git
cd defiende-el-servidor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/dvc pull -r dagshub      # modelos y datos; el repositorio es público, no pide token
.venv/bin/pytest
```

Si ya lo tienes clonado: `git pull` y `.venv/bin/dvc pull -r dagshub`.

## 2. Ver el proyecto andando

Para probar la API y la web juntas, en dos terminales:

```bash
.venv/bin/rally api                  # API en http://127.0.0.1:8000
cd web && npm ci && npm run dev      # web en http://localhost:5173
```

El visor anterior, con la vista del entrenamiento en vivo, sigue disponible con `.venv/bin/rally web`, en el puerto 8765.

Sin API, la versión compilada de la web entra en modo replay: `cd web && npm run build && npx vite preview`.

## 3. Colaborar

```bash
git switch main && git pull
git switch -c mi-rama
# cambios, pruebas
git push -u origin mi-rama
```

Une a `main` cuando pasen `pytest` y, si tocaste la web, `npm run build` dentro de `web/`.

Para subir experimentos o modelos hacen falta credenciales. Copia `.env.example` a `.env`, y configura DVC una vez:

```bash
dvc remote modify --local dagshub user TU_USUARIO
dvc remote modify --local dagshub password TU_TOKEN
```

## 4. Antes de entrenar

```bash
.venv/bin/dvc status
```

Revisa qué etapas se rehacen: si cambiaste `env.py`, `policies.py` o `pipeline.py`, puede reentrenar PPO. El
entrenamiento es pesado: 12 núcleos apagaron el computador por calor, así que limita la carga con `taskset`.

```bash
taskset -c 0-5 .venv/bin/dvc repro
```

Un experimento nuevo es: cambiar `params.yaml`, escribir antes la `hipotesis`, correr `dvc repro`, comparar en
MLflow y hacer commit de `params.yaml` y `dvc.lock`. Después:

```bash
.venv/bin/dvc push -r dagshub
.venv/bin/rally sincronizar        # copia MLflow a DagsHub; necesita DAGSHUB_TOKEN
.venv/bin/rally manifiesto         # actualiza el catálogo desde las etiquetas de git
```

## 5. Elegir y restaurar modelos

```bash
.venv/bin/rally seleccionar ppo-modelo-v5-s1 --tipo ppo --semilla 1   # aplica configs/seleccion.yaml
~/.venvs/rally-flujo/bin/python pipelines/flujo.py --rollback "motivo"
```

Prefect va en un entorno aparte: `python3 -m venv ~/.venvs/rally-flujo && ~/.venvs/rally-flujo/bin/pip install prefect pyyaml`.

El test reservado (`rally test-final`) ya se usó. No lo repitas: necesita una semilla que solo está en el `.env` de
Kevin, y volver a usarlo para ajustar modelos le quita su valor.

## 6. Publicar la web

La web en Vercel está conectada al fork `kevin-nieto-callejas/defiende-el-servidor`, porque Vercel no tiene acceso
al repositorio de Miguel. Publicarla requiere subir la versión a ese fork y desplegar desde Vercel:

- Root Directory: `web`
- Build: `npm run build`
- Output: `dist`

Después de cambiar modelos, regenera las vueltas grabadas con `.venv/bin/rally replays` antes de compilar.
Cuando exista la API, define `VITE_API_BASE_URL` en Vercel y la web dejará el modo replay.

## 7. Publicar la API

El destino está por acordar con el docente. El paquete se arma con:

```bash
.venv/bin/python deploy/api/empaquetar.py ../rally-space
```

Verifica el SHA-256 de cada modelo. El contenedor todavía no se ha construido.
