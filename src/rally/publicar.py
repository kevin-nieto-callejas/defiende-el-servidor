"""Publicación del modelo en Hugging Face Hub (`rally publicar`).

Sube el modelo PPO (models/ppo/modelo.zip) con una tarjeta de modelo (README)
que incluye métricas de la evaluación, parámetros y la versión de MLflow.
El token se lee de la variable HF_TOKEN o del archivo .env (que no se sube a git).
Cada publicación crea una etiqueta v<versión de MLflow> en el repositorio del Hub.
Con `vehiculo="moto"` sube el PPO de la moto (models/moto/ppo/) con sus métricas.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import yaml


def _token():
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    env = Path(".env")
    if env.exists():
        for linea in env.read_text(encoding="utf-8-sig").splitlines():
            if linea.strip().startswith("HF_TOKEN="):
                return linea.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Falta HF_TOKEN: agrégalo al archivo .env (HF_TOKEN=hf_...) o como variable de entorno.")


def tarjeta(info, ev, params, repo_id, vehiculo="carro"):
    ppo = ev["resultados"].get("ppo", {})
    seco, moj = ppo.get("seco", {}), ppo.get("mojado", {})
    moto = vehiculo == "moto"
    gym_id = "AutonomousRallyMoto-v0" if moto else "AutonomousRally-v0"
    quien = "una moto MotoGP (gira inclinándose; pasarse del agarre la tira)" if moto else "un carro"
    filas = "\n".join(
        f"| {p} | {r['seco']['vueltas_pct']} % | {r['seco']['tiempo_mediano_s'] or '—'} s | "
        f"{r['mojado']['vueltas_pct']} % | {r['mojado']['tiempo_mediano_s'] or '—'} s |"
        for p, r in ev["resultados"].items())
    return f"""---
library_name: stable-baselines3
tags:
- reinforcement-learning
- gymnasium
- stable-baselines3
- autonomous-driving
- mlops
model-index:
- name: PPO {gym_id} (Mónaco)
  results:
  - task:
      type: reinforcement-learning
      name: reinforcement-learning
    dataset:
      name: {gym_id} (circuito Mónaco, seco μ=0.9)
      type: {gym_id}
    metrics:
    - type: vueltas_completas_pct
      value: {seco.get('vueltas_pct')}
      name: Vueltas completas en seco (%)
    - type: vueltas_completas_pct
      value: {moj.get('vueltas_pct')}
      name: Vueltas completas en mojado (%)
---

# PPO · Autonomous Rally{' MotoGP' if moto else ''} (circuito inspirado en Mónaco)

Agente de aprendizaje por refuerzo que maneja {quien} en un circuito urbano de
1 049 m con 18 curvas, entrenado con **PPO** (Stable-Baselines3 + PyTorch) tras un
preentrenamiento por imitación. Proyecto del curso de MLOps.

- Ambiente: `{gym_id}` (Gymnasium) v{info.get("ambiente_version", "0.2")}, observación de {info.get("observacion", 24)} valores
  (velocidad, giro, rumbo, desvío, 7 rayos, 3 notas de curvatura, sensor de agarre y sensor de lluvia), acción continua
  `[acelerador, dirección]` en [-1, 1].
- Entrenamiento: {info.get('pasos')} pasos, {info.get('episodios')} episodios,
  {int(100 * params['ppo'].get('prob_lluvia', 0))} % de los episodios con lluvia (μ ∈ [{params['ppo'].get('lluvia_min')}, {params['ppo'].get('lluvia_max')}]),
  el resto en seco (μ ∈ [{params['ppo']['mu_min']}, {params['ppo']['mu_max']}]).
- MLflow: modelo `{info.get('mlflow_modelo')}` versión **{info.get('mlflow_version')}**,
  corrida `{info.get('mlflow_run_id')}`.

## Evaluación (protocolo de la ficha, {ev['episodios_por_condicion']} episodios por condición)

| Piloto | Seco: vueltas | Seco: tiempo mediano | Mojado: vueltas | Mojado: tiempo mediano |
|---|---|---|---|---|
{filas}

## Uso

```python
from huggingface_hub import hf_hub_download
from stable_baselines3 import PPO
import gymnasium as gym, rally

ruta = hf_hub_download("{repo_id}", "modelo.zip")
model = PPO.load(ruta)
env = gym.make("{gym_id}")
obs, _ = env.reset(seed=0)
accion, _ = model.predict(obs, deterministic=True)
```
"""


def _verificar_dvc(vehiculo="carro"):
    """No publica si el modelo o las métricas no corresponden al último `dvc repro`."""
    import subprocess
    import sys

    etapas = ["moto-ppo", "moto-evaluar"] if vehiculo == "moto" else ["ppo", "evaluar"]
    try:
        salida = subprocess.check_output([sys.executable, "-m", "dvc", "status", *etapas], text=True,
                                         stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as e:
        raise SystemExit(f"No se pudo verificar con DVC: {e}")
    if "up to date" not in salida.lower():
        raise SystemExit("El modelo o las métricas no están al día con DVC. Corre `dvc repro` antes "
                         f"de publicar.\n{salida}")


def publicar(repo_id, privado=True, vehiculo="carro"):
    from huggingface_hub import HfApi

    from rally import vehiculos

    _verificar_dvc(vehiculo)
    modelos, metricas = vehiculos.carpeta("models", vehiculo), vehiculos.carpeta("metrics", vehiculo)
    info = json.loads((modelos / "ppo/info.json").read_text(encoding="utf-8"))
    ev = json.loads((metricas / "evaluacion.json").read_text(encoding="utf-8"))
    if vehiculo == "moto":   # sección moto: encima de la del carro
        from rally.pipeline import params as leer_params
        params = leer_params("moto")
    else:
        params = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))
    api = HfApi(token=_token())
    api.create_repo(repo_id, private=privado, exist_ok=True)
    api.update_repo_settings(repo_id, private=privado)  # si el repo ya existía, aplica la visibilidad
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copy(modelos / "ppo/modelo.zip", tmp / "modelo.zip")
        shutil.copy(modelos / "ppo/info.json", tmp / "info.json")
        shutil.copy(metricas / "evaluacion.json", tmp / "evaluacion.json")
        shutil.copy("params.yaml", tmp / "params.yaml")
        (tmp / "README.md").write_text(tarjeta(info, ev, params, repo_id, vehiculo), encoding="utf-8")
        version = info.get("mlflow_version")
        commit = api.upload_folder(repo_id=repo_id, folder_path=tmp,
                                   commit_message=f"Modelo PPO v{version} (MLflow)")
    if version:
        # La etiqueta apunta a este commit; si ya existe (otra máquina con otro mlflow.db),
        # falla en vez de quedar apuntando a un modelo viejo.
        api.create_tag(repo_id, tag=f"v{version}", revision=commit.oid,
                       tag_message=f"MLflow run {info.get('mlflow_run_id')}", exist_ok=False)
    return f"https://huggingface.co/{repo_id}", commit
