"""Pipeline completo con Prefect: de validar el perfil a comprobar la versión servida.

Prefect orquesta; DVC decide qué etapas rehacer y `rally` hace el trabajo con el entorno del
proyecto. Cada tarea deja evidencia en runs/flujo/ aunque el flujo falle después.

    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --candidato ppo-modelo-v5 --tipo ppo
    ~/.venvs/rally-flujo/bin/python pipelines/flujo.py --rollback "motivo"
"""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from prefect import flow, get_run_logger, task

RAIZ = Path(__file__).resolve().parents[1]
RALLY = str(RAIZ / ".venv/bin/rally")
EVIDENCIA = RAIZ / "runs/flujo"


def _correr(*cmd, timeout=None):
    p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"{' '.join(cmd)} falló:\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
    return p.stdout


def _evidencia(etapa, datos):
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / f"{etapa}.json").write_text(json.dumps({"etapa": etapa, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **datos},
                                                        indent=2, ensure_ascii=False), encoding="utf-8")
    return datos


@task(name="1-validar")
def validar():
    salida = _correr(str(RAIZ / ".venv/bin/python"), "-c", (
        "import yaml; from rally.env import VERSION, OBS_DIM, AutonomousRallyEnv as E;"
        "p = yaml.safe_load(open('params.yaml')); yaml.safe_load(open('configs/seleccion.yaml'));"
        "e = E(**p['ambiente']); o = e.reset(seed=0)[0];"
        "assert o.shape == (OBS_DIM,) and e.observation_space.contains(o);"
        "print(VERSION, OBS_DIM)"))
    return _evidencia("validar", {"ambiente": salida.strip().splitlines()[-1]})


@task(name="2-pruebas")
def pruebas():
    return _evidencia("pruebas", {"resultado": _correr(str(RAIZ / ".venv/bin/pytest"), "-q").strip().splitlines()[-1]})


@task(name="3-entrenar-y-evaluar", retries=1, retry_delay_seconds=60)
def entrenar():
    """DVC reanuda desde el punto de guardado y no repite las etapas que ya están al día."""
    log = get_run_logger()
    salida = _correr(str(RAIZ / ".venv/bin/dvc"), "repro")
    log.info(salida[-500:])
    return _evidencia("entrenar", {"cola": salida.strip().splitlines()[-1]})


@task(name="4-registrar-manifiestos")
def registrar():
    return _evidencia("registrar", {"salida": _correr(RALLY, "manifiesto").strip().splitlines()[-3:]})


@task(name="5-seleccionar")
def seleccionar(candidato, tipo):
    salida = _correr(RALLY, "seleccionar", candidato, "--tipo", tipo)
    return _evidencia("seleccionar", json.loads(salida[salida.index("{"):]))


@task(name="6-promover")
def promover(veredicto):
    if not veredicto["aceptado"]:
        return _evidencia("promover", {"promovido": False, "veredicto": veredicto})
    salida = _correr(RALLY, "seleccionar", veredicto["candidato"], "--tipo", veredicto["tipo"], "--promover")
    return _evidencia("promover", {"promovido": True, "salida": salida[-300:]})


@task(name="7-publicar-catalogo")
def publicar():
    return _evidencia("publicar", {"catalogo": json.loads((RAIZ / "manifests/catalogo.json").read_text(encoding="utf-8"))[-1]["nombre"]})


@task(name="8-comprobar-version-servida", retries=2, retry_delay_seconds=5)
def comprobar(api):
    """Lo que dice la API es lo que cuenta: si no coincide con el recomendado, el flujo falla."""
    with urllib.request.urlopen(f"{api}/api/salud", timeout=20) as r:
        s = json.load(r)
    esperado = json.loads((RAIZ / "manifests/recomendado.json").read_text(encoding="utf-8"))["modelo"]
    if s["recomendado"].get("modelo") != esperado:
        raise RuntimeError(f"La API sirve {s['recomendado'].get('modelo')} y se esperaba {esperado}")
    return _evidencia("comprobar", {"servido": esperado, "commit": s["commit"], "ambiente": s["ambiente"]})


@flow(name="autonomous-rally")
def pipeline(candidato: str, tipo: str = "ppo", api: str = "http://127.0.0.1:8000", sin_entrenar: bool = False):
    validar()
    pruebas()
    if not sin_entrenar:
        entrenar()
    registrar()
    veredicto = seleccionar(candidato, tipo)
    promover(veredicto)
    publicar()
    return comprobar(api)


@flow(name="autonomous-rally-rollback")
def rollback(motivo: str, api: str = "http://127.0.0.1:8000"):
    _evidencia("rollback", {"salida": _correr(RALLY, "seleccionar", "--rollback", motivo)[-300:]})
    return comprobar(api)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--candidato")
    a.add_argument("--tipo", default="ppo")
    a.add_argument("--api", default="http://127.0.0.1:8000")
    a.add_argument("--sin-entrenar", action="store_true")
    a.add_argument("--rollback")
    x = a.parse_args()
    if x.rollback:
        print(rollback(x.rollback, x.api))
    else:
        print(pipeline(x.candidato, x.tipo, x.api, x.sin_entrenar))
