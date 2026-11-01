"""Test final reservado: se corre una sola vez, con los modelos ya elegidos.

Las semillas viven en RALLY_SEMILLA_RESERVADA (archivo .env, fuera del repositorio público), así
ningún ajuste de parámetros pudo verlas. Solo se publica su SHA-256, que permite comprobar después
que el test usó esas semillas. Un segundo intento exige `--repetir` y queda anotado.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from rally.pipeline import METRICAS, _escribir_json

SALIDA = METRICAS / "test-final.json"
N = 100


def semilla_reservada():
    if os.environ.get("RALLY_SEMILLA_RESERVADA"):
        return int(os.environ["RALLY_SEMILLA_RESERVADA"])
    for linea in Path(".env").read_text(encoding="utf-8").splitlines():
        if linea.startswith("RALLY_SEMILLA_RESERVADA="):
            return int(linea.split("=", 1)[1])
    raise SystemExit("Falta RALLY_SEMILLA_RESERVADA en .env")


def correr(modelos, repetir=False):
    """modelos: {nombre: (tipo, ruta de los pesos)}."""
    from rally.semillas import evaluar

    previo = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else None
    if previo and not repetir:
        raise SystemExit("El test final ya se corrió: usa --repetir solo con una razón y déjala anotada")
    base = semilla_reservada()
    res = {"episodios": N, "semillas_sha256": hashlib.sha256(str(base).encode()).hexdigest(),
           "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "corridas": (previo or {}).get("corridas", 0) + 1,
           "resultados": {n: evaluar(t, r, list(range(base, base + N))) for n, (t, r) in modelos.items()}}
    _escribir_json(SALIDA, res)
    return res
