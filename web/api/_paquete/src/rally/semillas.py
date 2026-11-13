"""Contraste de finalistas: el mismo experimento con otras semillas de entrenamiento.

La semilla 0 sale de `dvc repro`. Aquí se entrenan las demás y cada una se evalúa con la misma
suite. Son entrenamientos independientes, no episodios de un solo modelo. El resultado se
acumula en metrics/semillas.json, y una semilla ya terminada no se repite tras un apagón.
Con `vehiculo="moto"` todo va a metrics/moto/ y models/moto/semillas/.
"""
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from rally import track, vehiculos
from rally.generalizacion import _nucleos
from rally.pipeline import METRICAS, _config_ambiente, _escribir_json, _evaluador_rapido, _metricas, _run, params, rutas

SALIDA = Path(os.environ.get("RALLY_SEMILLAS", METRICAS / "semillas.json"))  # uno por agente si corren a la vez
SEMILLAS_EVAL = list(range(100))


def salida(vehiculo="carro"):
    if vehiculo == "carro":
        return SALIDA
    return Path(os.environ.get("RALLY_SEMILLAS", rutas(vehiculo)["metricas"] / "semillas.json"))


def _piloto(tipo, ruta):
    if tipo == "ppo":
        from rally.agentes.ppo import PilotoPPO
        return PilotoPPO(ruta)
    from rally.agentes.qlearning import AgenteQ
    return AgenteQ.cargar(ruta)


def _caso(args):
    tipo, ruta, ambiente, prueba, semillas, *resto = args
    vehiculo = resto[0] if resto else "carro"
    pol = _piloto(tipo, ruta)
    env = vehiculos.crear_env(vehiculo, **{**ambiente, **prueba.get("ambiente", {})})
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
                    "inc": info["off_track_events"] + (info["outcome"] in ("choque", "caida")),
                    "prog": info["s_best"] / track.largo(info)})
    return prueba["nombre"], out


def evaluar(tipo, ruta, semillas=None, vehiculo="carro"):
    semillas = SEMILLAS_EVAL if semillas is None else semillas
    p = params(vehiculo)
    amb, pe, pg = p["ambiente"], p["evaluacion"], p["generalizacion"]
    pruebas = [{"nombre": "seco", "ambiente": {"mu": pe["mu_seco"]}},
               {"nombre": "mojado", "ambiente": {"mu": pe["mu_mojado"]}}] + pg["pruebas"]
    tareas = [(tipo, str(ruta), amb, pr, semillas[i:i + 10], vehiculo) for pr in pruebas for i in range(0, len(semillas), 10)]
    filas = {}
    with ProcessPoolExecutor(max_workers=_nucleos()) as ex:
        for nombre, out in ex.map(_caso, tareas):
            filas.setdefault(nombre, []).extend(out)
    return {n: _metricas(f) for n, f in filas.items()}


def _entrenar(tipo, s, vehiculo="carro"):
    p = params(vehiculo)
    r_ = rutas(vehiculo)
    amb, pt = p["ambiente"], {**p[tipo], "semilla": s}
    salida = r_["modelos"] / "semillas" / f"{tipo}-s{s}"
    salida.mkdir(parents=True, exist_ok=True)
    punto_dir = str(r_["runs"] / "semillas" / f"{tipo}-s{s}")
    with _run(f"{tipo}-semilla-{s}", pt, {"algoritmo": tipo, "hipotesis": pt["hipotesis"], "contraste": "finalistas"},
              vehiculo):
        if tipo == "ppo":
            from rally.agentes import ppo
            demos = r_["demos"]
            huella = hashlib.sha1(json.dumps([amb, pt, vehiculos.version(vehiculo), _config_ambiente(vehiculo)[1]],
                                             sort_keys=True).encode() + demos.read_bytes()).hexdigest()[:16]
            ppo.entrenar(amb, pt, demos, salida, None,
                         _evaluador_rapido(amb, p["evaluacion"], pistas=pt.get("pistas"), vehiculo=vehiculo),
                         ppo.PuntoGuardado(punto_dir, huella))
            return salida / "modelo.zip"
        from rally.agentes.qlearning import entrenar
        ag, _ = entrenar(lambda: vehiculos.crear_env(vehiculo, **amb), pt, carpeta_punto=punto_dir)
        ag.guardar(salida / "q_table.npz")
        return salida / "q_table.npz"


def correr(tipo, semillas, vehiculo="carro"):
    destino = salida(vehiculo)
    res = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    for s in semillas:
        clave = f"{tipo}-s{s}"
        if clave in res:
            print(f"  {clave}: ya estaba")
            continue
        ruta = _entrenar(tipo, s, vehiculo)
        res[clave] = evaluar(tipo, ruta, vehiculo=vehiculo)
        _escribir_json(destino, res)   # tras cada semilla: un apagón no la pierde
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
