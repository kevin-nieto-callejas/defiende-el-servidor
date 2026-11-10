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

from rally import historicos, policies, track
from rally.env import VERSION
from rally.web import PistaNoDisponible, correr_episodio, datos_pista, leer_parametros, leer_pista

RECOMENDADO = Path("manifests/recomendado.json")
MODOS = {"aleatoria": "aleatorio", "experto": "referencia", "prudente": "referencia", "maestro": "referencia"}
MAX_EPISODIOS = 20

app = FastAPI(title="Autonomous Rally API", version=VERSION)
origenes = [o for o in os.environ.get("RALLY_ORIGENES", "*").split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["GET", "POST"], allow_headers=["*"])

# En Vercel cada instancia de la función lleva su propia cuenta: el monitoreo dice desde cuándo
monitor = {"episodios": 0, "errores": 0, "por_modelo": {}, "fallos": {}, "latencia_ms": [],
           "instancia_desde": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
PAQUETE = Path("paquete.json")   # lo escribe deploy/api/empaquetar.py: commit del que salió el paquete


def paquete():
    return json.loads(PAQUETE.read_text(encoding="utf-8")) if PAQUETE.exists() else None


def commit_servido():
    """Commit desplegado: el que fija el contenedor, el que entrega Vercel o el de git en local."""
    for var in ("RALLY_COMMIT", "VERCEL_GIT_COMMIT_SHA"):
        if os.environ.get(var):
            return os.environ[var]
    if paquete():
        return paquete()["commit"]
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
        return lambda semilla: policies.crear(nombre, semilla), MODOS[nombre], "reglas"
    try:
        pol = historicos.piloto(nombre)
    except KeyError:
        raise HTTPException(404, f"No existe la versión {nombre}") from None
    except historicos.SinAdaptador as e:
        raise HTTPException(409, f"{nombre} no tiene adaptador validado: {e}") from None
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(503, str(e)) from None
    return lambda semilla: pol, "evaluacion", pol.motor


def _pista(nombre):
    """Pista pedida: 403 si es la reservada para la prueba, 404 si no existe."""
    try:
        return leer_pista(nombre)
    except PistaNoDisponible as e:
        raise HTTPException(403 if (nombre or "").strip().lower() in track.RESERVADAS else 404, str(e)) from None


def _identidad(nombre, params, modo, motor):
    m = historicos.manifiesto(nombre) if nombre not in MODOS else {}
    return {"modelo": nombre, "modo": modo, "motor": motor, "ambiente_servido": VERSION,
            "commit_servido": commit_servido(),
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
    pista: str = "monaco"


@app.get("/api/salud")
def salud():
    lat = monitor["latencia_ms"]
    p = paquete()
    return {"estado": "ok", "ambiente": VERSION, "commit": commit_servido(), "recomendado": recomendado(),
            "commit_paquete": p["commit"] if p else None, "instancia_desde": monitor["instancia_desde"],
            "episodios": monitor["episodios"], "errores": monitor["errores"],
            "latencia_paso_ms": round(float(np.mean(lat)), 3) if lat else None}


@app.get("/api/monitoreo")
def monitoreo():
    return {**monitor, "latencia_ms": None, **salud()}


@app.get("/api/pista")
def pista(pista: str = "monaco"):
    d = datos_pista(_pista(pista))
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
             a_max: float = 4.0, r_max: float = 20.0, pista: str = "monaco"):
    modelo = piloto
    pista = _pista(pista)
    crear, modo, motor = _politica(modelo)
    params = dict(ancho=ancho, mu=mu, a_max=a_max, r_max=r_max)
    t0 = time.perf_counter()
    try:
        ep = correr_episodio(modelo, semilla, politica=crear(semilla), pista=pista, **params)
    except Exception as e:
        monitor["errores"] += 1
        raise HTTPException(500, f"Falló la simulación: {e}") from e
    ms = 1000 * (time.perf_counter() - t0) / max(len(ep["frames"]), 1)
    _registrar(modelo, ep["resultado"], ms)
    return {**ep, **_identidad(modelo, {**leer_parametros(params), "pista": pista}, modo, motor),
            "id": monitor["episodios"],
            "latencia_paso_ms": round(ms, 3)}


@app.post("/api/evaluar")
def evaluar(e: Evaluacion):
    """Evaluación del modelo congelado: resultados por caso, no una demostración elegida."""
    crear, modo, motor = _politica(e.modelo)
    pista = _pista(e.pista)
    params = dict(ancho=e.ancho, mu=e.mu, a_max=e.a_max, r_max=e.r_max)
    casos, t0 = [], time.perf_counter()
    for s in range(e.semilla_inicial, e.semilla_inicial + e.episodios):
        ep = correr_episodio(e.modelo, s, politica=crear(s), pista=pista, **params)
        _registrar(e.modelo, ep["resultado"], 0.0)
        casos.append({k: ep[k] for k in ("semilla", "resultado", "tiempo", "recompensa", "salidas", "progreso")})
    fines = {}
    for c in casos:
        fines[c["resultado"]] = fines.get(c["resultado"], 0) + 1
    tiempos = [c["tiempo"] for c in casos if c["resultado"] == "exito"]
    return {**_identidad(e.modelo, {**leer_parametros(params), "pista": pista}, modo, motor), "casos": casos,
            "fallos_por_causa": fines,
            "vueltas_pct": round(100 * len(tiempos) / e.episodios, 1),
            "tiempo_mediano_s": float(np.median(tiempos)) if tiempos else None,
            "segundos": round(time.perf_counter() - t0, 2)}
