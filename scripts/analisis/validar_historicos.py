"""¿Cada versión, corriendo por su adaptador, reproduce lo que dice su manifiesto?"""
import json
import os
from concurrent.futures import ProcessPoolExecutor

from rally import historicos
from rally.env import AutonomousRallyEnv

N = 20


def medir(args):
    nombre, mu = args
    try:
        pol = historicos.piloto(nombre)
    except (historicos.SinAdaptador, FileNotFoundError) as e:
        return nombre, mu, None, None, str(e)[:60]
    env = AutonomousRallyEnv(mu=mu)
    ok, t = 0, []
    for s in range(N):
        obs, info = env.reset(seed=s)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        ok += info["outcome"] == "exito"
        if info["outcome"] == "exito":
            t.append(info["t"])
    return nombre, mu, 100 * ok / N, round(sorted(t)[len(t) // 2], 1) if t else None, ""


if __name__ == "__main__":
    cat = {c["nombre"]: c for c in historicos.catalogo()}
    tareas = [(n, mu) for n in cat for mu in (0.9, 0.5)]
    with ProcessPoolExecutor(max_workers=8) as ex:
        filas = list(ex.map(medir, tareas))
    salida = []
    for n, mu, pct, t, nota in filas:
        guardado = (cat[n]["resultados"] or {}).get("seco" if mu == 0.9 else "mojado") or {}
        coincide = pct is not None and abs(pct - guardado.get("vueltas_pct", -999)) <= 20
        salida.append({"nombre": n, "mu": mu, "medido_pct": pct, "tiempo": t, "guardado_pct": guardado.get("vueltas_pct"),
                       "guardado_t": guardado.get("tiempo_mediano_s"), "coincide": coincide, "nota": nota})
        print(f"{n:34s} μ {mu} medido {pct}% {t}s · guardado {guardado.get('vueltas_pct')}% {guardado.get('tiempo_mediano_s')}s "
              f"{'OK' if coincide else 'DIFIERE'} {nota}", flush=True)
    json.dump(salida, open("runs/logs/validar_historicos.json", "w"), indent=1)
    print("VALIDACION_LISTA")
