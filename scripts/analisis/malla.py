"""Mide PPO y Q-learning en toda la zona de los deslizadores del visor (no reentrena nada)."""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from rally import policies, track
from rally.env import AutonomousRallyEnv

SEMILLAS = list(range(3000, 3020))  # distintas a ficha, entrenamiento y generalización
BASE = {"track_width": 8.0, "a_max": 4.0, "r_max": 20.0}


def condiciones():
    out = [{"mu": m} for m in (0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9, 1.0)]
    for mu in (0.9, 0.5):
        out += [{"mu": mu, "track_width": v} for v in (6.0, 7.0, 10.0, 12.0)]
        out += [{"mu": mu, "a_max": v} for v in (2.0, 3.0, 5.0, 6.0)]
        out += [{"mu": mu, "r_max": v} for v in (10.0, 15.0, 30.0, 40.0)]
    return out


def lote(args):
    piloto, cond = args
    env = AutonomousRallyEnv(**{**BASE, **cond})
    fin, prog, sitios = {}, [], {}
    for s in SEMILLAS:
        pol = policies.crear(piloto, s)
        obs, info = env.reset(seed=s)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        fin[info["outcome"]] = fin.get(info["outcome"], 0) + 1
        prog.append(info["s_best"] / track.LAP)
        if info["outcome"] != "exito":
            k = str(round(info["s_best"] / 25) * 25)
            sitios[k] = sitios.get(k, 0) + 1
    return {"piloto": piloto, "cond": cond, "ok_pct": 100 * fin.get("exito", 0) / len(SEMILLAS),
            "fin": fin, "prog": round(sum(prog) / len(prog), 3), "sitios": sitios}


if __name__ == "__main__":
    pilotos = sys.argv[1].split(",")
    tareas = [(p, c) for p in pilotos for c in condiciones()]
    with ProcessPoolExecutor(max_workers=len(os.sched_getaffinity(0))) as ex:
        filas = list(ex.map(lote, tareas))
    json.dump(filas, open(f"docs/evidencia/modelos/malla-{'-'.join(pilotos)}.json", "w"), indent=1)
    for f in filas:
        print(f"{f['piloto']:10s} {str(f['cond']):38s} {f['ok_pct']:5.0f}% prog={f['prog']:.2f} {f['fin']}")
    print("MALLA_LISTA")
