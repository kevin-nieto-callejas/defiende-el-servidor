"""Pipeline completo con Prefect: de validar el perfil a comprobar la versión servida.

Prefect orquesta; DVC decide qué etapas rehacer y `rally` hace el trabajo con el entorno del
proyecto. Cada tarea deja evidencia en runs/flujo/ aunque el flujo falle después.

    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --candidato ppo-modelo-v5 --tipo ppo
    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --rollback "motivo"
    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --comprobar https://autonomous-rally.vercel.app

Moto MotoGP: el mismo flujo con `--vehiculo moto` (etapas moto-* de DVC, selección en manifests/moto/):

    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --vehiculo moto --candidato ppo-moto-v1 --tipo ppo
    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --vehiculo moto --rollback "motivo"
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from prefect import flow, get_run_logger, task

RAIZ = Path(__file__).resolve().parents[1]
RALLY = str(RAIZ / ".venv/bin/rally")
EVIDENCIA = RAIZ / "runs/flujo"


def _correr(*cmd, timeout=None):
    # Un hilo de PyTorch por proceso: con varios procesos y muchos hilos, la generalización tardó 10 veces más
    entorno = {**os.environ, "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout, env=entorno)
    if p.returncode:
        raise RuntimeError(f"{' '.join(cmd)} falló:\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
    return p.stdout


def _evidencia(etapa, datos, vehiculo="carro"):
    etapa = etapa if vehiculo == "carro" else f"moto-{etapa}"
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / f"{etapa}.json").write_text(json.dumps({"etapa": etapa, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **datos},
                                                        indent=2, ensure_ascii=False), encoding="utf-8")
    return datos


@task(name="1-validar")
def validar(vehiculo="carro"):
    salida = _correr(str(RAIZ / ".venv/bin/python"), "-c", (
        "import yaml; from rally import vehiculos as V; from rally.pipeline import params;"
        f"v = '{vehiculo}'; p = params(v); yaml.safe_load(open('configs/seleccion.yaml'));"
        "e = V.crear_env(v, **p['ambiente']); o = e.reset(seed=0)[0];"
        "assert o.shape == (V.n_obs(v),) and e.observation_space.contains(o);"
        "print(V.version(v), V.n_obs(v))"))
    return _evidencia("validar", {"ambiente": salida.strip().splitlines()[-1]}, vehiculo)


@task(name="2-pruebas")
def pruebas():
    return _evidencia("pruebas", {"resultado": _correr(str(RAIZ / ".venv/bin/pytest"), "-q").strip().splitlines()[-1]})


@task(name="3-entrenar-y-evaluar", retries=1, retry_delay_seconds=60)
def entrenar(vehiculo="carro"):
    """DVC reanuda desde el punto de guardado y no repite las etapas que ya están al día."""
    log = get_run_logger()
    etapas = ["moto-registrar", "moto-generalizacion"] if vehiculo == "moto" else []
    salida = _correr(str(RAIZ / ".venv/bin/dvc"), "repro", *etapas)
    log.info(salida[-500:])
    return _evidencia("entrenar", {"cola": salida.strip().splitlines()[-1]}, vehiculo)


@task(name="4-registrar-manifiestos")
def registrar(vehiculo="carro"):
    extra = ["--vehiculo", "moto"] if vehiculo == "moto" else []
    return _evidencia("registrar", {"salida": _correr(RALLY, "manifiesto", *extra).strip().splitlines()[-3:]}, vehiculo)


@task(name="5-seleccionar")
def seleccionar(candidato, tipo, vehiculo="carro"):
    salida = _correr(RALLY, "seleccionar", candidato, "--tipo", tipo, "--anotar",   # aceptado o no, queda anotado
                     "--vehiculo", vehiculo)
    return _evidencia("seleccionar", json.loads(salida[salida.index("{"):]), vehiculo)


@task(name="6-promover")
def promover(veredicto, vehiculo="carro"):
    if not veredicto["aceptado"]:
        return _evidencia("promover", {"promovido": False, "veredicto": veredicto}, vehiculo)
    salida = _correr(RALLY, "seleccionar", veredicto["candidato"], "--tipo", veredicto["tipo"], "--promover",
                     "--vehiculo", vehiculo)
    return _evidencia("promover", {"promovido": True, "salida": salida[-300:]}, vehiculo)


@task(name="7-publicar-catalogo")
def publicar():
    """Catálogo y paquete de la API de Vercel (código, manifiestos y modelos en numpy, verificados)."""
    _correr(str(RAIZ / ".venv/bin/python"), "deploy/api/empaquetar.py", "web/api/_paquete", "--vercel", timeout=1800)
    paquete = json.loads((RAIZ / "web/api/_paquete/paquete.json").read_text(encoding="utf-8"))
    return _evidencia("publicar", {
        "catalogo": json.loads((RAIZ / "manifests/catalogo.json").read_text(encoding="utf-8"))[-1]["nombre"],
        "paquete_vercel": {"commit": paquete["commit"], "huella_src": paquete["huella_src"],
                           "modelos": {k: v["npz_sha256"] for k, v in paquete["modelos"].items()}},
        "siguiente_paso": "revisar el diff, hacer commit y push a la rama de Vercel; luego --comprobar <url>",
    })


@task(name="8-comprobar-version-servida", retries=2, retry_delay_seconds=5)
def comprobar(api, vehiculo="carro"):
    """Lo que dice la API es lo que cuenta: si no coincide con el recomendado, el flujo falla."""
    with urllib.request.urlopen(f"{api}/api/salud", timeout=20) as r:
        s = json.load(r)
    ruta = "manifests/moto/recomendado.json" if vehiculo == "moto" else "manifests/recomendado.json"
    esperado = json.loads((RAIZ / ruta).read_text(encoding="utf-8"))["modelo"]
    servido = s["vehiculos"]["moto"]["recomendado"] if vehiculo == "moto" else s["recomendado"].get("modelo")
    if servido != esperado:
        raise RuntimeError(f"La API sirve {servido} y se esperaba {esperado}")
    ambiente = s["vehiculos"]["moto"]["ambiente"] if vehiculo == "moto" else s["ambiente"]
    return _evidencia("comprobar", {"servido": esperado, "commit": s["commit"], "ambiente": ambiente}, vehiculo)


@flow(name="autonomous-rally")
def pipeline(candidato: str, tipo: str = "ppo", api: str = "http://127.0.0.1:8000", sin_entrenar: bool = False,
             vehiculo: str = "carro"):
    validar(vehiculo)
    pruebas()
    if not sin_entrenar:
        entrenar(vehiculo)
    registrar(vehiculo)
    veredicto = seleccionar(candidato, tipo, vehiculo)
    promover(veredicto, vehiculo)
    publicar()
    return comprobar(api, vehiculo)


@flow(name="autonomous-rally-rollback")
def rollback(motivo: str, api: str = "http://127.0.0.1:8000", vehiculo: str = "carro"):
    _evidencia("rollback", {"salida": _correr(RALLY, "seleccionar", "--rollback", motivo, "--vehiculo", vehiculo)[-300:]},
               vehiculo)
    publicar()   # la web publicada también debe servir la versión restaurada
    return comprobar(api, vehiculo)


@flow(name="autonomous-rally-comprobar")
def comprobar_publicada(api: str, vehiculo: str = "carro"):
    """Después del despliegue: la URL pública sirve el modelo recomendado del repositorio."""
    return comprobar(api, vehiculo)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--candidato")
    a.add_argument("--tipo", default="ppo")
    a.add_argument("--api", default="http://127.0.0.1:8000")
    a.add_argument("--sin-entrenar", action="store_true")
    a.add_argument("--rollback")
    a.add_argument("--comprobar", metavar="URL", help="solo comprobar la versión que sirve esa URL")
    a.add_argument("--vehiculo", choices=["carro", "moto"], default="carro")
    x = a.parse_args()
    if x.comprobar:
        print(comprobar_publicada(x.comprobar.rstrip("/"), x.vehiculo))
    elif x.rollback:
        print(rollback(x.rollback, x.api, x.vehiculo))
    else:
        print(pipeline(x.candidato, x.tipo, x.api, x.sin_entrenar, x.vehiculo))
