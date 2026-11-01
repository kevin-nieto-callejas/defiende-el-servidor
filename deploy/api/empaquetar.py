"""Arma la carpeta que se sube al Space: código, manifiestos y pesos nombrados por SHA-256.

Uso: .venv/bin/python deploy/api/empaquetar.py <carpeta-salida>
Verifica el SHA-256 de cada peso: si algo no coincide, no se empaqueta. El commit queda en
RALLY_COMMIT para que la API diga exactamente qué versión está sirviendo.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from rally.historicos import catalogo
from rally.manifiesto import _cache

RAIZ = Path(__file__).resolve().parents[2]
PAQUETES = ("gymnasium", "numpy", "scipy", "rich", "torch", "stable_baselines3", "cloudpickle", "fastapi",
            "uvicorn", "pydantic", "PyYAML", "pandas", "matplotlib")


def requisitos():
    fijos = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in fijos if l.split("==")[0].lower() in {p.lower() for p in PAQUETES}) + "\n"


def main(destino):
    d = Path(destino)
    d.mkdir(parents=True, exist_ok=True)
    (d / "pesos").mkdir(exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RAIZ).strip()
    shutil.copy(RAIZ / "deploy/api/Dockerfile", d)
    shutil.copy(RAIZ / "pyproject.toml", d)
    (d / "requirements-api.txt").write_text(requisitos(), encoding="utf-8")
    (d / "README.md").write_text("---\ntitle: Autonomous Rally API\nsdk: docker\napp_port: 7860\n---\n\n"
                                 f"API de simulación del proyecto Autonomous Rally. Commit `{commit}`.\n", encoding="utf-8")
    shutil.rmtree(d / "src", ignore_errors=True)
    shutil.copytree(RAIZ / "src", d / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "static"))
    shutil.rmtree(d / "manifests", ignore_errors=True)
    shutil.copytree(RAIZ / "manifests", d / "manifests")
    texto = (d / "Dockerfile").read_text(encoding="utf-8").replace("RALLY_MODELOS=/app/pesos", f"RALLY_MODELOS=/app/pesos RALLY_COMMIT={commit}")
    (d / "Dockerfile").write_text(texto, encoding="utf-8")
    for f in catalogo():
        if not f["ejecutable"]:
            continue
        m = json.loads((RAIZ / "manifests" / f"{f['nombre']}.json").read_text(encoding="utf-8"))
        origen = RAIZ / _cache(m["model_md5_dvc"])
        if hashlib.sha256(origen.read_bytes()).hexdigest() != m["model_sha256"]:
            raise SystemExit(f"SHA-256 no coincide: {f['nombre']}")
        shutil.copy(origen, d / "pesos" / m["model_sha256"])
        print(f"  {f['nombre']}: {m['model_sha256'][:12]}")
    print(f"Listo para subir: {d} (commit {commit[:8]})")


if __name__ == "__main__":
    main(sys.argv[1])
