"""Prueba de sobreajuste: ¿el piloto maneja bien en condiciones que nunca practicó?

La evaluación de la ficha (seco μ 0.9, mojado μ 0.5) usa condiciones que están dentro de lo que
el PPO vio al entrenar (seco 0.75–1.0, lluvia 0.45–0.6). Aquí se cambian cosas que nunca vio:
agarre fuera de esos rangos, salidas más torcidas y ruido en los sensores. Si el modelo solo
memorizó lo que practicó, se cae en estas pruebas; si aprendió a manejar, se mantiene.

Cada prueba se compara con su condición de referencia (seco o mojado). Una caída de más de
`caida_max` puntos en vueltas completas se marca como sobreajuste.
"""
import json
import os
from concurrent.futures import ProcessPoolExecutor

import mlflow
import numpy as np

from rally import policies, track
from rally.env import AutonomousRallyEnv
from rally.pipeline import METRICAS, _escribir_json, _metricas, _run, params


def _lote(args):
    piloto, ambiente, prueba, semillas = args
    env = AutonomousRallyEnv(**{**ambiente, **prueba.get("ambiente", {})})
    ruido = prueba.get("ruido_sensores", 0.0)
    out = []
    for s in semillas:
        pol = policies.crear(piloto, s)
        rng = np.random.default_rng(s)
        obs, info = env.reset(seed=s)
        total, done = 0.0, False
        while not done:
            if ruido:
                obs = (obs + rng.normal(0.0, ruido, obs.shape)).astype(np.float32)
            obs, r, term, trunc, info = env.step(pol(obs, info))
            total += r
            done = term or trunc
        out.append({"ok": info["outcome"] == "exito", "t": info["t"], "r": total,
                    "inc": info["off_track_events"] + (info["outcome"] == "choque"),
                    "prog": info["s_best"] / track.LAP})
    return piloto, prueba["nombre"], out


def _nucleos():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def etapa_generalizacion():
    p = params()
    amb, pg, pe = p["ambiente"], p["generalizacion"], p["evaluacion"]
    pilotos = [x for x in pg["pilotos"] if policies.disponible(x)]
    semillas = list(range(pg["semilla_inicial"], pg["semilla_inicial"] + pg["episodios"]))
    pruebas = [{"nombre": "seco", "ambiente": {"mu": pe["mu_seco"]}},
               {"nombre": "mojado", "ambiente": {"mu": pe["mu_mojado"]}}] + pg["pruebas"]
    tareas = [(piloto, amb, prueba, semillas[i:i + 10])
              for piloto in pilotos for prueba in pruebas for i in range(0, len(semillas), 10)]
    filas = {}
    with ProcessPoolExecutor(max_workers=_nucleos()) as ex:
        for piloto, nombre, out in ex.map(_lote, tareas):
            filas.setdefault((piloto, nombre), []).extend(out)

    res, veredictos = {}, {}
    for piloto in pilotos:
        res[piloto] = {pr["nombre"]: _metricas(filas[(piloto, pr["nombre"])]) for pr in pruebas}
        detalle = {}
        for pr in pg["pruebas"]:
            ref = pr.get("referencia")
            if not ref:  # prueba informativa (más difícil que todo lo visto): sin veredicto
                continue
            caida = round(res[piloto][ref]["vueltas_pct"] - res[piloto][pr["nombre"]]["vueltas_pct"], 1)
            detalle[pr["nombre"]] = {"referencia": ref, "caida_puntos": caida,
                                     "aguanta": caida <= pg["caida_max"]}
        veredictos[piloto] = {"pruebas": detalle,
                              "sobreajuste": not all(d["aguanta"] for d in detalle.values())}

    salida = {"episodios_por_prueba": len(semillas), "caida_max_puntos": pg["caida_max"],
              "pruebas": {pr["nombre"]: pr for pr in pruebas},
              "resultados": res, "veredictos": veredictos}
    _escribir_json(METRICAS / "generalizacion.json", salida)
    with _run("generalizacion", pg):
        for piloto, cond in res.items():
            for c, m in cond.items():
                mlflow.log_metrics({f"{piloto}.{c}.{k}": v for k, v in m.items() if v is not None})
            mlflow.log_metric(f"{piloto}.sobreajuste", int(veredictos[piloto]["sobreajuste"]))
        mlflow.log_artifact(str(METRICAS / "generalizacion.json"))

    nombres = [pr["nombre"] for pr in pruebas]
    print("  " + " " * 10 + " ".join(f"{n[:11]:>11s}" for n in nombres))
    for piloto, cond in res.items():
        marca = "SOBREAJUSTE" if veredictos[piloto]["sobreajuste"] else "generaliza"
        print(f"  {piloto:10s}" + " ".join(f"{cond[n]['vueltas_pct']:10.1f}%" for n in nombres)
              + f"  → {marca}")
    return salida


if __name__ == "__main__":
    print(json.dumps(etapa_generalizacion()["veredictos"], indent=2, ensure_ascii=False))
