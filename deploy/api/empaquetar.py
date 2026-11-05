"""Arma la carpeta de la API publicada: código, manifiestos y pesos nombrados por SHA-256.

Uso:
  .venv/bin/python deploy/api/empaquetar.py ../rally-space                 # contenedor (Docker): PyTorch
  python deploy/api/empaquetar.py ../rally-api --sin-pesos                  # contenedor de prueba (CI): solo pilotos de referencia
  .venv/bin/python deploy/api/empaquetar.py web/api/_paquete --vercel      # función de Vercel: solo numpy
  .venv/bin/python deploy/api/empaquetar.py web/api/_paquete --verificar   # ¿el paquete coincide con el repo?

Verifica el SHA-256 de cada peso contra su manifiesto: si algo no coincide, no se empaqueta.

Contenedor: copia los pesos originales y fija el commit en RALLY_COMMIT.
Vercel: una función no puede cargar PyTorch (pesa más que el límite), así que cada modelo va como
`pesos/<sha256 del original>.npz`, una exportación a numpy que guarda ese SHA-256. La red de PPO se
compara contra PyTorch antes de escribirse (agentes/red_numpy.py); las tablas Q ya son numpy.
`paquete.json` dice de qué commit salió el paquete y cómo se verificó cada modelo.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from rally.agentes.red_numpy import exportar, sha256
from rally.historicos import catalogo
from rally.manifiesto import _cache

RAIZ = Path(__file__).resolve().parents[2]
PAQUETES = ("gymnasium", "numpy", "scipy", "rich", "torch", "stable_baselines3", "cloudpickle", "fastapi",
            "uvicorn", "pydantic", "PyYAML", "pandas", "matplotlib")
IGNORAR = shutil.ignore_patterns("__pycache__", "*.egg-info", "static", "*.pyc")


def requisitos():
    fijos = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in fijos if l.split("==")[0].lower() in {p.lower() for p in PAQUETES}) + "\n"


def huella(carpeta):
    """SHA-256 de un árbol de archivos (rutas y contenido), sin cachés de Python ni el visor."""
    h = hashlib.sha256()
    for f in sorted(Path(carpeta).rglob("*")):
        rel = f.relative_to(carpeta)
        if f.is_dir() or {"__pycache__", "static"} & set(rel.parts) or f.suffix == ".pyc" or ".egg-info" in str(rel):
            continue
        h.update(str(rel).replace("\\", "/").encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def manifiestos_ejecutables():
    for f in catalogo():
        if f["ejecutable"]:
            yield json.loads((RAIZ / "manifests" / f"{f['nombre']}.json").read_text(encoding="utf-8"))


def original(m):
    """Pesos originales desde la caché de DVC, con su SHA-256 comprobado."""
    ruta = RAIZ / _cache(m["model_md5_dvc"])
    if not ruta.exists():
        raise SystemExit(f"Faltan los pesos de {m['nombre']}: corre `dvc pull -r dagshub` primero")
    if sha256(ruta) != m["model_sha256"]:
        raise SystemExit(f"SHA-256 no coincide: {m['nombre']}")
    return ruta


def copiar_codigo(d):
    shutil.rmtree(d / "src", ignore_errors=True)
    shutil.copytree(RAIZ / "src", d / "src", ignore=IGNORAR)
    shutil.rmtree(d / "manifests", ignore_errors=True)
    shutil.copytree(RAIZ / "manifests", d / "manifests")


def contenedor(d, commit, con_pesos=True):
    (d / "pesos").mkdir(exist_ok=True)
    shutil.copy(RAIZ / "deploy/api/Dockerfile", d)
    shutil.copy(RAIZ / "pyproject.toml", d)
    (d / "requirements-api.txt").write_text(requisitos(), encoding="utf-8")
    (d / "README.md").write_text("---\ntitle: Autonomous Rally API\nsdk: docker\napp_port: 7860\n---\n\n"
                                 f"API de simulación del proyecto Autonomous Rally. Commit `{commit}`.\n", encoding="utf-8")
    copiar_codigo(d)
    texto = (d / "Dockerfile").read_text(encoding="utf-8").replace("RALLY_MODELOS=/app/pesos", f"RALLY_MODELOS=/app/pesos RALLY_COMMIT={commit}")
    (d / "Dockerfile").write_text(texto, encoding="utf-8")
    if not con_pesos:
        print("  sin pesos: las versiones del catálogo responderán 503 (pesos no disponibles)")
        return
    for m in manifiestos_ejecutables():
        shutil.copy(original(m), d / "pesos" / m["model_sha256"])
        print(f"  {m['nombre']}: {m['model_sha256'][:12]}")


def _fuente(ruta):
    with np.load(ruta, allow_pickle=False) as z:
        return str(z["fuente_sha256"]) if "fuente_sha256" in z.files else None


def vercel(d, commit):
    """Paquete sin PyTorch. Un .npz que ya corresponde a su modelo no se reescribe: el zip lleva la hora."""
    pesos = d / "pesos"
    pesos.mkdir(parents=True, exist_ok=True)
    copiar_codigo(d)
    modelos = {}
    for m in manifiestos_ejecutables():
        destino = pesos / f"{m['model_sha256']}.npz"
        if destino.exists() and _fuente(destino) == m["model_sha256"]:
            previo = d / "paquete.json"
            anterior = json.loads(previo.read_text(encoding="utf-8"))["modelos"].get(m["nombre"]) if previo.exists() else None
            if anterior:
                modelos[m["nombre"]] = anterior
                print(f"  {m['nombre']}: ya exportado")
                continue
        fuente = original(m)
        if m["tipo"] == "ppo":
            info = exportar(fuente, destino) | {"motor": "numpy"}
        else:
            with np.load(fuente, allow_pickle=False) as z:
                np.savez_compressed(destino, q=z["q"], fuente_sha256=np.str_(m["model_sha256"]))
            info = {"fuente_sha256": m["model_sha256"], "npz_sha256": sha256(destino), "motor": "tabla"}
        modelos[m["nombre"]] = info
        print(f"  {m['nombre']}: {info['motor']}, {destino.stat().st_size / 1e6:.1f} MB"
              + (f", diferencia con PyTorch {info['max_diferencia']:.1e}" if "max_diferencia" in info else ""))
    for sobra in set(pesos.glob("*.npz")) - {pesos / f"{i['fuente_sha256']}.npz" for i in modelos.values()}:
        sobra.unlink()
    (d / "paquete.json").write_text(json.dumps({
        "commit": commit, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "destino": "vercel",
        "huella_src": huella(d / "src"), "huella_manifests": huella(d / "manifests"), "modelos": modelos,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verificar(d):
    """El paquete publicado debe ser el código, los manifiestos y los modelos de este repositorio."""
    errores = []
    if huella(d / "src") != huella(RAIZ / "src"):
        errores.append("src/ del paquete no coincide con src/ del repositorio")
    if huella(d / "manifests") != huella(RAIZ / "manifests"):
        errores.append("manifests/ del paquete no coincide con el repositorio")
    for m in manifiestos_ejecutables():
        ruta = d / "pesos" / f"{m['model_sha256']}.npz"
        if not ruta.exists():
            errores.append(f"falta el modelo {m['nombre']}")
        elif _fuente(ruta) != m["model_sha256"]:
            errores.append(f"{ruta.name} no se exportó del modelo de {m['nombre']}")
    return errores


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("destino")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--vercel", action="store_true", help="paquete sin PyTorch para la función de Vercel")
    modo.add_argument("--verificar", action="store_true", help="comprueba un paquete existente")
    modo.add_argument("--sin-pesos", action="store_true", help="contenedor sin modelos, para probar la construcción")
    a = ap.parse_args(argv)
    d = Path(a.destino)
    if a.verificar:
        errores = verificar(d)
        for e in errores:
            print(f"  ✗ {e}")
        print("Paquete al día con el repositorio" if not errores else "Paquete desactualizado: vuelve a empaquetar")
        return 1 if errores else 0
    d.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RAIZ).strip()
    if a.vercel:
        vercel(d, commit)
    else:
        contenedor(d, commit, con_pesos=not a.sin_pesos)
    print(f"Listo: {d} (commit {commit[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
