"""Maestro con control de tracción: limita el pedal para no gastar todo el agarre en acelerar."""
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from rally.env import AutonomousRallyEnv
from rally.policies import G, PurePursuit

BASE = {"track_width": 8.0, "a_max": 4.0, "r_max": 20.0}
SEMILLAS = range(3000, 3006)
SECO = [{"mu": m} for m in (0.75, 0.9, 1.0)] + [{"mu": 0.9, "a_max": a} for a in (2.0, 6.0)]
MOJADO = [{"mu": m} for m in (0.4, 0.45, 0.5, 0.7)] + [{"mu": m, "a_max": 6.0} for m in (0.4, 0.5, 0.7)] \
    + [{"mu": 0.4, "a_max": 2.0}, {"mu": 0.4, "track_width": 6.0}, {"mu": 0.4, "track_width": 12.0}]
CANDIDATOS = [("seco", m, f, SECO) for m in (0.8, 0.72) for f in (0.8,)] \
    + [("mojado", m, f, MOJADO) for m in (0.45, 0.42, 0.38) for f in (0.85, 0.7, 0.55)]


class ConTraccion(PurePursuit):
    def __init__(self, supuesto, frac, a_max):
        super().__init__(supuesto)
        self.tope = frac * supuesto * G
        self.a_max = a_max

    def __call__(self, obs, info):
        u = super().__call__(obs, info)
        a = u[0] * (self.a_max if u[0] >= 0 else 8.0)
        a = max(-self.tope, min(self.tope, a))
        return np.array([a / (self.a_max if a >= 0 else 8.0), u[1]], dtype=np.float32)


def lote(args):
    tipo, supuesto, frac, cond = args
    c = {**BASE, **cond}
    env = AutonomousRallyEnv(**c)
    pol = ConTraccion(supuesto, frac, c["a_max"])
    ok, t, fines = 0, [], {}
    for s in SEMILLAS:
        obs, info = env.reset(seed=s)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        ok += info["outcome"] == "exito"
        fines[info["outcome"]] = fines.get(info["outcome"], 0) + 1
        if info["outcome"] == "exito":
            t.append(info["t"])
    return tipo, supuesto, frac, cond, ok, sum(t) / len(t) if t else None, fines


if __name__ == "__main__":
    tareas = [(tipo, m, f, c) for tipo, m, f, conds in CANDIDATOS for c in conds]
    with ProcessPoolExecutor(max_workers=len(os.sched_getaffinity(0))) as ex:
        for tipo, m, f, c, ok, t, fines in ex.map(lote, tareas):
            print(f"{tipo:6s} {m:.2f} frac {f:.2f} {str(c):34s} {ok}/6 t={t and round(t, 1)} {fines if ok < 6 else ''}", flush=True)
    print("LISTO")
