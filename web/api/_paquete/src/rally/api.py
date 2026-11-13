"""API de simulación e inferencia (FastAPI): Python es la autoridad del mundo.

La web de Vercel consulta el catálogo, carga una versión y ejecuta episodios con el mismo
ambiente del entrenamiento. Cada respuesta dice qué modelo, ambiente y modo la produjo.

Dos vehículos: el carro y la moto MotoGP. `vehiculo=moto` en /api/pista, /api/episodio,
/api/evaluar y /api/modelos. Un modelo del catálogo trae su vehículo en el manifiesto: si no se
pide vehículo se usa el suyo, y pedirle el otro responde 409 (sus observaciones no coinciden).
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

from rally import historicos, policies, track, vehiculos
from rally.env import VERSION
from rally.web import PistaNoDisponible, correr_episodio, datos_pista, leer_parametros, leer_pista

RECOMENDADO = Path("manifests/recomendado.json")
RECOMENDADO_MOTO = Path("manifests/moto/recomendado.json")
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


def recomendado(vehiculo="carro"):
    ruta = RECOMENDADO_MOTO if vehiculo == "moto" else RECOMENDADO
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"modelo": None, "motivo": "todavía no se ha promovido una versión"}


def _vehiculo(nombre):
    """Vehículo pedido; 404 si no existe."""
    try:
        return vehiculos.validar(nombre)
    except ValueError as e:
        raise HTTPException(404, str(e)) from None


def _vehiculo_de(nombre, pedido=None):
    """Vehículo con que corre un piloto: el pedido, o el del manifiesto de la versión.

    Una versión de un vehículo no corre en el otro: su contrato de observaciones es otro (24 o 26).
    """
    if nombre in MODOS:
        return _vehiculo(pedido)
    try:
        propio = historicos.vehiculo(historicos.manifiesto(nombre))
    except KeyError:
        raise HTTPException(404, f"No existe la versión {nombre}") from None
    if pedido is not None and _vehiculo(pedido) != propio:
        raise HTTPException(409, f"{nombre} se entrenó con el vehículo {propio}: no corre en el vehículo {pedido}")
    return propio


def _politica(nombre, vehiculo="carro"):
    """Piloto de referencia o versión del catálogo; errores como HTTP, nunca un replay disfrazado."""
    if nombre in MODOS:
        return lambda semilla: policies.crear(nombre, semilla, vehiculo), MODOS[nombre], "reglas"
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


def _identidad(nombre, params, modo, motor, vehiculo="carro"):
    m = historicos.manifiesto(nombre) if nombre not in MODOS else {}
    return {"modelo": nombre, "modo": modo, "motor": motor, "vehiculo": vehiculo,
            "ambiente_servido": vehiculos.version(vehiculo), "commit_servido": commit_servido(),
            "ambiente_del_modelo": m.get("environment_version"), "model_sha256": m.get("model_sha256"),
            "adaptador": bool(m) and m["contrato"]["observaciones"] != vehiculos.n_obs(vehiculo), "params": params}


def _registrar(nombre, resultado, ms):
    monitor["episodios"] += 1
    monitor["por_modelo"][nombre] = monitor["por_modelo"].get(nombre, 0) + 1
    monitor["fallos"][resultado] = monitor["fallos"].get(resultado, 0) + 1
    monitor["latencia_ms"] = (monitor["latencia_ms"] + [ms])[-500:]


class Evaluacion(BaseModel):
    modelo: str
    episodios: int = Field(10, ge=1, le=MAX_EPISODIOS)
    semilla_inicial: int = Field(0, ge=0)
    # Sin valor se usa la base del vehículo (la moto acelera 5 m/s², el carro 4)
    ancho: float | None = None
    mu: float | None = None
    a_max: float | None = None
    r_max: float | None = None
    pista: str = "monaco"
    vehiculo: str | None = None


def _condiciones(**kw):
    return {k: v for k, v in kw.items() if v is not None}


@app.get("/api/salud")
def salud():
    lat = monitor["latencia_ms"]
    p = paquete()
    return {"estado": "ok", "ambiente": VERSION, "commit": commit_servido(), "recomendado": recomendado(),
            "vehiculos": {v: {"ambiente": vehiculos.version(v), "recomendado": recomendado(v).get("modelo")}
                          for v in vehiculos.VEHICULOS},
            "commit_paquete": p["commit"] if p else None, "instancia_desde": monitor["instancia_desde"],
            "episodios": monitor["episodios"], "errores": monitor["errores"],
            "latencia_paso_ms": round(float(np.mean(lat)), 3) if lat else None}


@app.get("/api/monitoreo")
def monitoreo():
    return {**monitor, "latencia_ms": None, **salud()}


@app.get("/api/pista")
def pista(pista: str = "monaco", vehiculo: str = "carro"):
    vehiculo = _vehiculo(vehiculo)
    d = datos_pista(_pista(pista), vehiculo)
    versiones = {f["nombre"]: f"{f['level_id']} · {f['decision']}" for f in historicos.catalogo()
                 if f["ejecutable"] and f["vehiculo"] == vehiculo}
    d["pilotos"] = {**{k: policies.politicas(vehiculo)[k][0] for k in MODOS}, **versiones}
    d["recomendado"] = recomendado(vehiculo).get("modelo")
    return d


@app.get("/api/modelos")
def modelos(vehiculo: str | None = None):
    """Catálogo: todo (por defecto) o solo las versiones de un vehículo."""
    if vehiculo is None:
        return {"recomendado": recomendado(), "modelos": historicos.catalogo(), "referencias": list(MODOS),
                "recomendados": {v: recomendado(v) for v in vehiculos.VEHICULOS}}
    vehiculo = _vehiculo(vehiculo)
    return {"recomendado": recomendado(vehiculo), "vehiculo": vehiculo, "referencias": list(MODOS),
            "modelos": [f for f in historicos.catalogo() if f["vehiculo"] == vehiculo]}


@app.get("/api/modelos/{nombre}")
def modelo(nombre: str):
    try:
        return historicos.manifiesto(nombre)
    except KeyError:
        raise HTTPException(404, f"No existe la versión {nombre}") from None


@app.get("/api/episodio")
def episodio(piloto: str, semilla: int = Query(0, ge=0), ancho: float | None = None, mu: float | None = None,
             a_max: float | None = None, r_max: float | None = None, pista: str = "monaco",
             vehiculo: str | None = None):
    modelo = piloto
    vehiculo = _vehiculo_de(modelo, vehiculo)
    pista = _pista(pista)
    crear, modo, motor = _politica(modelo, vehiculo)
    params = _condiciones(ancho=ancho, mu=mu, a_max=a_max, r_max=r_max)
    t0 = time.perf_counter()
    try:
        ep = correr_episodio(modelo, semilla, politica=crear(semilla), pista=pista, vehiculo=vehiculo, **params)
    except Exception as e:
        monitor["errores"] += 1
        raise HTTPException(500, f"Falló la simulación: {e}") from e
    ms = 1000 * (time.perf_counter() - t0) / max(len(ep["frames"]), 1)
    _registrar(modelo, ep["resultado"], ms)
    return {**ep, **_identidad(modelo, {**leer_parametros(params, vehiculo), "pista": pista}, modo, motor, vehiculo),
            "id": monitor["episodios"],
            "latencia_paso_ms": round(ms, 3)}


@app.post("/api/evaluar")
def evaluar(e: Evaluacion):
    """Evaluación del modelo congelado: resultados por caso, no una demostración elegida."""
    vehiculo = _vehiculo_de(e.modelo, e.vehiculo)
    crear, modo, motor = _politica(e.modelo, vehiculo)
    pista = _pista(e.pista)
    params = _condiciones(ancho=e.ancho, mu=e.mu, a_max=e.a_max, r_max=e.r_max)
    casos, t0 = [], time.perf_counter()
    for s in range(e.semilla_inicial, e.semilla_inicial + e.episodios):
        ep = correr_episodio(e.modelo, s, politica=crear(s), pista=pista, vehiculo=vehiculo, **params)
        _registrar(e.modelo, ep["resultado"], 0.0)
        casos.append({k: ep[k] for k in ("semilla", "resultado", "tiempo", "recompensa", "salidas", "progreso")})
    fines = {}
    for c in casos:
        fines[c["resultado"]] = fines.get(c["resultado"], 0) + 1
    tiempos = [c["tiempo"] for c in casos if c["resultado"] == "exito"]
    return {**_identidad(e.modelo, {**leer_parametros(params, vehiculo), "pista": pista}, modo, motor, vehiculo),
            "casos": casos,
            "fallos_por_causa": fines,
            "vueltas_pct": round(100 * len(tiempos) / e.episodios, 1),
            "tiempo_mediano_s": float(np.median(tiempos)) if tiempos else None,
            "segundos": round(time.perf_counter() - t0, 2)}
