"""Transmisión en vivo del entrenamiento hacia el visor 3D.

Mientras el agente entrena, se guarda cada episodio terminado (paso a paso) y la
curva de aprendizaje en runs/vivo/. El visor (`rally web`) los lee y los dibuja,
así se ve cómo el modelo mejora episodio a episodio.
"""

import json
import os
import time
from pathlib import Path

import numpy as np

from rally.env import RAYO_REF

CARPETA = Path("runs/vivo")


def _guardar(nombre, datos):
    CARPETA.mkdir(parents=True, exist_ok=True)
    tmp = CARPETA / f".{nombre}.tmp"
    tmp.write_text(json.dumps(datos, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, CARPETA / nombre)  # escritura atómica: el visor nunca lee a medias


class Grabador:
    """Acumula los pasos de un episodio en el formato que dibuja el visor."""

    def __init__(self, agente, params):
        self.agente = agente
        self.params = params
        self.frames = []
        self.total = 0.0
        self.curva = []
        self.n_episodio = 0
        self.inicio = time.time()

    def paso(self, obs, info, accion, r):
        self.total += r
        self.frames.append({
            "t": round(info["t"], 2), "x": round(info["x"], 3), "y": round(info["y"], 3),
            "psi": round(info["psi"], 4), "v": round(info["v"], 3), "d": round(info["d"], 3),
            "s": round(max(info["s_best"], 0), 2), "cp": info["next_cp"],
            "agarre": round(info["grip_use"], 3), "derrape": bool(info["skidding"]),
            "fuera": round(info["off_steps"] * 0.1, 2),
            "rayos": [round(float(v) * RAYO_REF, 3) for v in np.asarray(obs)[6:13]],
            "a": [round(float(accion[0]), 3), round(float(accion[1]), 3)],
            "r": round(float(r), 3), "R": round(self.total, 2), "fin": info["outcome"],
        })

    def fin(self, info, pasos_totales, extra=None):
        from rally import track

        self.n_episodio += 1
        resumen = {
            "episodio": self.n_episodio, "pasos_totales": int(pasos_totales),
            "resultado": info["outcome"], "tiempo": round(info["t"], 2),
            "recompensa": round(self.total, 2),
            "progreso": round(max(info["s_best"], 0) / track.LAP * 100, 1),
        }
        self.curva.append(resumen)
        _guardar("episodio.json", {
            "agente": self.agente, "piloto": f"{self.agente} (entrenando)", "semilla": 0,
            "params": self.params, "id": self.n_episodio, **resumen,
            "salidas": info["off_track_events"], "frames": self.frames,
        })
        _guardar("curva.json", {
            "agente": self.agente, "segundos": round(time.time() - self.inicio, 1),
            "episodios": self.curva[-2000:], **(extra or {}),
        })
        self.frames, self.total = [], 0.0
        return resumen
