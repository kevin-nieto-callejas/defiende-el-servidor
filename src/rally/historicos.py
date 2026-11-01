"""Carga cualquier versión del catálogo como piloto, con el contrato de su familia.

Los pesos se buscan por SHA-256 en RALLY_MODELOS (el despliegue) o en la caché de DVC. Las
familias viejas corren sobre el ambiente actual con un adaptador: reciben solo sus primeras
observaciones y los rayos divididos por el alcance, como en su ambiente original.
`runs/validar_historicos.py` compara cada adaptador contra los resultados guardados.
"""
import json
import os
from pathlib import Path

import numpy as np

from rally.agentes.discreto import ACCIONES, NEUTRA, a_mando
from rally.env import RAYO_REF
from rally.manifiesto import SALIDA, _cache

# Discretización de la tabla v6 (familia 0.3): sin margen de frenada, con curvatura a 50 m
_BINS_V6 = [(4, (-0.6, -0.3, -0.1, 0.1, 0.3, 0.6)), (5, (-0.08, -0.04, -0.015, 0.015, 0.04, 0.08)),
            (0, (0.2, 0.3, 0.4, 0.5, 0.6, 0.72, 0.85)), (14, (-0.4, -0.12, 0.12, 0.4)),
            (13, (-0.4, -0.12, 0.12, 0.4)), (15, (-0.4, -0.12, 0.12, 0.4)), (19, (0.5,))]
_FORMA_V6 = tuple(len(b) + 1 for _, b in _BINS_V6)


class SinAdaptador(Exception):
    """Esa versión no se puede ejecutar aquí; el catálogo la muestra solo como evidencia."""


def ejecutable(entrada):
    """Las tablas anteriores a la v6 usan otra discretización: quedan solo como evidencia."""
    return (entrada["tipo"] == "ppo" or "qlearning" in entrada["etiqueta_git"]
            or entrada["environment_version"].startswith("0.4"))


def catalogo():
    filas = json.loads((SALIDA / "catalogo.json").read_text(encoding="utf-8"))
    return [{**f, "ejecutable": ejecutable(f)} for f in filas]


def manifiesto(nombre):
    ruta = SALIDA / f"{Path(nombre).name}.json"
    if not ruta.exists():
        raise KeyError(nombre)
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ubicar(m):
    base = os.environ.get("RALLY_MODELOS")
    candidatas = [Path(base) / m["model_sha256"]] if base else []
    candidatas.append(_cache(m["model_md5_dvc"]))
    for c in candidatas:
        if c.exists():
            return c
    raise FileNotFoundError(f"pesos de {m['nombre']} no disponibles")


def adaptar(obs, n_obs):
    """Observación actual (24) → la que espera un modelo de n_obs valores."""
    o = np.asarray(obs, dtype=np.float32)
    if n_obs == len(o):
        return o
    a = o[:n_obs].copy()
    a[6:13] *= RAYO_REF / (o[22] * RAYO_REF)
    return a


class _PPOHistorico:
    def __init__(self, ruta):
        from stable_baselines3 import PPO
        self.model = PPO.load(ruta, device="cpu")
        self.n_obs = self.model.observation_space.shape[0]

    def __call__(self, obs, info):
        a, _ = self.model.predict(adaptar(obs, self.n_obs), deterministic=True)
        return np.clip(a, -1, 1)


class _TablaHistorica:
    def __init__(self, ruta):
        self.q = np.load(ruta)["q"]
        if self.q.shape == (int(np.prod(_FORMA_V6)), len(ACCIONES)):
            self.actual = False
        elif self.q.shape[1] == len(ACCIONES) and self.q.shape[0] == 117_600:
            self.actual = True
        else:
            raise SinAdaptador(f"tabla {self.q.shape}: discretización anterior a la v6")

    def __call__(self, obs, info):
        if self.actual:
            from rally.agentes.discreto import estado
            s = estado(obs)
        else:
            s = int(np.ravel_multi_index([int(np.digitize(obs[i], b)) for i, b in _BINS_V6], _FORMA_V6))
        fila = self.q[s]
        accion = ACCIONES[NEUTRA if fila[NEUTRA] == fila.max() else int(np.argmax(fila))]
        return a_mando(accion, obs) if self.actual else accion


_pilotos = {}


def piloto(nombre):
    """Piloto de esa versión; se carga una sola vez."""
    if nombre not in _pilotos:
        m = manifiesto(nombre)
        ruta = _ubicar(m)
        _pilotos[nombre] = _PPOHistorico(ruta) if m["tipo"] == "ppo" else _TablaHistorica(ruta)
    return _pilotos[nombre]
