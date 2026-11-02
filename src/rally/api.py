"""API de simulación e inferencia (FastAPI): Python es la autoridad del mundo.

La web de Vercel consulta el catálogo, carga una versión y ejecuta episodios con el mismo
ambiente del entrenamiento. Cada respuesta dice qué modelo, ambiente y modo la produjo.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rally import historicos, policies
from rally.env import VERSION
from rally.web import correr_episodio, datos_pista, leer_parametros

RECOMENDADO = Path("manifests/recomendado.json")
MODOS = {"aleatoria": "aleatorio", "experto": "referencia", "prudente": "referencia", "maestro": "referencia"}
MAX_EPISODIOS = 20

app = FastAPI(title="Autonomous Rally API", version=VERSION)
origenes = [o for o in os.environ.get("RALLY_ORIGENES", "*").split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["GET", "POST"], allow_headers=["*"])

monitor = {"episodios": 0, "errores": 0, "por_modelo": {}, "fallos": {}, "latencia_ms": []}


def commit_servido():
    env = os.environ.get("RALLY_COMMIT")
    if env:
        return env
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"


def recomendado():
    if RECOMENDADO.exists():
        return json.loads(RECOMENDADO.read_text(encoding="utf-8"))
    return {"modelo": None, "motivo": "todavía no se ha promovido una versión"}


def _politica(nombre):
    """Piloto de referencia o versión del catálogo; errores como HTTP, nunca un replay disfrazado."""
    if nombre in MODOS:
        return lambda semilla: policies.crear(nombre, semilla), MODOS[nombre]
    try:
        pol = historicos.piloto(nombre)
    except KeyError:
        raise HTTPException(404, f"No existe la versión {nombre}") from None
    except historicos.SinAdaptador as e:
        raise HTTPException(409, f"{nombre} no tiene adaptador validado: {e}") from None
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from None
    return lambda semilla: pol, "evaluacion"


def _identidad(nombre, params, modo):
    m = historicos.manifiesto(nombre) if nombre not in MODOS else {}
    return {"modelo": nombre, "modo": modo, "ambiente_servido": VERSION, "commit_servido": commit_servido(),
            "ambiente_del_modelo": m.get("environment_version"), "model_sha256": m.get("model_sha256"),
            "adaptador": bool(m) and m["contrato"]["observaciones"] != 24, "params": params}


def _registrar(nombre, resultado, ms):
    monitor["episodios"] += 1
    monitor["por_modelo"][nombre] = monitor["por_modelo"].get(nombre, 0) + 1
    monitor["fallos"][resultado] = monitor["fallos"].get(resultado, 0) + 1
    monitor["latencia_ms"] = (monitor["latencia_ms"] + [ms])[-500:]


class Evaluacion(BaseModel):
    modelo: str
    episodios: int = Field(10, ge=1, le=MAX_EPISODIOS)
    semilla_inicial: int = Field(0, ge=0)
    ancho: float = 8.0
    mu: float = 0.9
    a_max: float = 4.0
    r_max: float = 20.0


@app.get("/api/salud")
def salud():
    lat = monitor["latencia_ms"]
    return {"estado": "ok", "ambiente": VERSION, "commit": commit_servido(), "recomendado": recomendado(),
            "episodios": monitor["episodios"], "errores": monitor["errores"],
            "latencia_paso_ms": round(float(np.mean(lat)), 3) if lat else None}


@app.get("/api/monitoreo")
def monitoreo():
    return {**monitor, "latencia_ms": None, **salud()}


@app.get("/api/pista")
def pista():
    d = datos_pista()
    versiones = {f["nombre"]: f"{f['level_id']} · {f['decision']}" for f in historicos.catalogo() if f["ejecutable"]}
    d["pilotos"] = {**{k: policies.POLITICAS[k][0] for k in MODOS}, **versiones}
    d["recomendado"] = recomendado().get("modelo")
    return d


@app.get("/api/modelos")
def modelos():
    return {"recomendado": recomendado(), "modelos": historicos.catalogo(), "referencias": list(MODOS)}


@app.get("/api/modelos/{nombre}")
def modelo(nombre: str):
    try:
        return historicos.manifiesto(nombre)
    except KeyError:
        raise HTTPException(404, f"No existe la versión {nombre}") from None


@app.get("/api/episodio")
def episodio(piloto: str, semilla: int = Query(0, ge=0), ancho: float = 8.0, mu: float = 0.9,
             a_max: float = 4.0, r_max: float = 20.0):
    modelo = piloto
    crear, modo = _politica(modelo)
    params = dict(ancho=ancho, mu=mu, a_max=a_max, r_max=r_max)
    t0 = time.perf_counter()
    try:
        ep = correr_episodio(modelo, semilla, politica=crear(semilla), **params)
    except Exception as e:
        monitor["errores"] += 1
        raise HTTPException(500, f"Falló la simulación: {e}") from e
    ms = 1000 * (time.perf_counter() - t0) / max(len(ep["frames"]), 1)
    _registrar(modelo, ep["resultado"], ms)
    return {**ep, **_identidad(modelo, leer_parametros(params), modo), "id": monitor["episodios"],
            "latencia_paso_ms": round(ms, 3)}


@app.post("/api/evaluar")
def evaluar(e: Evaluacion):
    """Evaluación del modelo congelado: resultados por caso, no una demostración elegida."""
    crear, modo = _politica(e.modelo)
    params = dict(ancho=e.ancho, mu=e.mu, a_max=e.a_max, r_max=e.r_max)
    casos, t0 = [], time.perf_counter()
    for s in range(e.semilla_inicial, e.semilla_inicial + e.episodios):
        ep = correr_episodio(e.modelo, s, politica=crear(s), **params)
        _registrar(e.modelo, ep["resultado"], 0.0)
        casos.append({k: ep[k] for k in ("semilla", "resultado", "tiempo", "recompensa", "salidas", "progreso")})
    fines = {}
    for c in casos:
        fines[c["resultado"]] = fines.get(c["resultado"], 0) + 1
    tiempos = [c["tiempo"] for c in casos if c["resultado"] == "exito"]
    return {**_identidad(e.modelo, leer_parametros(params), modo), "casos": casos, "fallos_por_causa": fines,
            "vueltas_pct": round(100 * len(tiempos) / e.episodios, 1),
            "tiempo_mediano_s": float(np.median(tiempos)) if tiempos else None,
            "segundos": round(time.perf_counter() - t0, 2)}
