"""Seguimiento de experimentos con MLflow.

Todo queda en el repositorio local: base de datos `mlflow.db` (experimentos,
métricas y registro de modelos) y artefactos en `mlruns/`. Ninguno de los dos
se sube a git; la interfaz se abre con `rally mlflow`.
"""

import os
import subprocess
from pathlib import Path

import mlflow

TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENTO = "autonomous-rally-monaco"
MODELOS = {"qlearning": "rally-qlearning", "ppo": "rally-ppo"}


def iniciar():
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", TRACKING_URI))
    if mlflow.get_experiment_by_name(EXPERIMENTO) is None:
        mlflow.create_experiment(EXPERIMENTO, artifact_location=Path("mlruns").resolve().as_uri())
    mlflow.set_experiment(EXPERIMENTO)


def etiquetas_git():
    """Commit y estado del repo: liga cada corrida al código exacto que la produjo."""
    def git(*a):
        try:
            return subprocess.check_output(["git", *a], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return "desconocido"
    return {"git_commit": git("rev-parse", "HEAD"),
            "git_rama": git("rev-parse", "--abbrev-ref", "HEAD"),
            "git_sucio": str(bool(git("status", "--porcelain")))}


def aplanar(d, prefijo=""):
    out = {}
    for k, v in d.items():
        clave = f"{prefijo}{k}"
        if isinstance(v, dict):
            out.update(aplanar(v, clave + "."))
        else:
            out[clave] = v
    return out
