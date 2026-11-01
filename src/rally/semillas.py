"""Contraste de finalistas: el mismo experimento con otras semillas de entrenamiento.

La semilla 0 sale de `dvc repro`. Aquí se entrenan las demás y cada una se evalúa con la misma
suite. Son entrenamientos independientes, no episodios de un solo modelo. El resultado se
acumula en metrics/semillas.json, y una semilla ya terminada no se repite tras un apagón.
"""
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from rally import track
from rally.env import VERSION, AutonomousRallyEnv
from rally.generalizacion import _nucleos
from rally.pipeline import DEMOS, METRICAS, _config_ambiente, _escribir_json, _evaluador_rapido, _metricas, _run, params

SALIDA = METRICAS / "semillas.json"
SEMILLAS_EVAL = list(range(100))


def _piloto(tipo, ruta):
    if tipo == "ppo":
        from rally.agentes.ppo import PilotoPPO
        return PilotoPPO(ruta)
    from rally.agentes.qlearning import AgenteQ
    return AgenteQ.cargar(ruta)


def _caso(args):
    tipo, ruta, ambiente, prueba, semillas = args
    pol = _piloto(tipo, ruta)
    env = AutonomousRallyEnv(**{**ambiente, **prueba.get("ambiente", {})})
    ruido, out = prueba.get("ruido_sensores", 0.0), []
    for s in semillas:
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
    return prueba["nombre"], out


def evaluar(tipo, ruta):
    p = params()
    amb, pe, pg = p["ambiente"], p["evaluacion"], p["generalizacion"]
    pruebas = [{"nombre": "seco", "ambiente": {"mu": pe["mu_seco"]}},
               {"nombre": "mojado", "ambiente": {"mu": pe["mu_mojado"]}}] + pg["pruebas"]
    tareas = [(tipo, str(ruta), amb, pr, SEMILLAS_EVAL[i:i + 10]) for pr in pruebas for i in range(0, 100, 10)]
    filas = {}
    with ProcessPoolExecutor(max_workers=_nucleos()) as ex:
        for nombre, out in ex.map(_caso, tareas):
            filas.setdefault(nombre, []).extend(out)
    return {n: _metricas(f) for n, f in filas.items()}


def _entrenar(tipo, s):
    p = params()
    amb, pt = p["ambiente"], {**p[tipo], "semilla": s}
    salida = Path(f"models/semillas/{tipo}-s{s}")
    salida.mkdir(parents=True, exist_ok=True)
    punto_dir = f"runs/semillas/{tipo}-s{s}"
    with _run(f"{tipo}-semilla-{s}", pt, {"algoritmo": tipo, "hipotesis": pt["hipotesis"], "contraste": "finalistas"}):
        if tipo == "ppo":
            from rally.agentes import ppo
            huella = hashlib.sha1(json.dumps([amb, pt, VERSION, _config_ambiente()[1]], sort_keys=True).encode()
                                  + DEMOS.read_bytes()).hexdigest()[:16]
            ppo.entrenar(amb, pt, DEMOS, salida, None, _evaluador_rapido(amb, p["evaluacion"]),
                         ppo.PuntoGuardado(punto_dir, huella))
            return salida / "modelo.zip"
        from rally.agentes.qlearning import entrenar
        ag, _ = entrenar(lambda: AutonomousRallyEnv(**amb), pt, carpeta_punto=punto_dir)
        ag.guardar(salida / "q_table.npz")
        return salida / "q_table.npz"


def correr(tipo, semillas):
    res = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {}
    for s in semillas:
        clave = f"{tipo}-s{s}"
        if clave in res:
            print(f"  {clave}: ya estaba")
            continue
        ruta = _entrenar(tipo, s)
        res[clave] = evaluar(tipo, ruta)
        _escribir_json(SALIDA, res)   # tras cada semilla: un apagón no la pierde
        m = res[clave]
        print(f"  {clave}: seco {m['seco']['vueltas_pct']}% · mojado {m['mojado']['vueltas_pct']}%", flush=True)
    return res


def resumen(res):
    """Media y desviación por finalista: distinguir suerte de una semilla y mejora real."""
    out = {}
    for tipo in sorted({k.rsplit("-s", 1)[0] for k in res}):
        filas = [v for k, v in res.items() if k.rsplit("-s", 1)[0] == tipo]
        out[tipo] = {c: {"media_pct": round(float(np.mean([f[c]["vueltas_pct"] for f in filas])), 1),
                         "desviacion_pct": round(float(np.std([f[c]["vueltas_pct"] for f in filas])), 1)}
                     for c in filas[0]}
    return out
