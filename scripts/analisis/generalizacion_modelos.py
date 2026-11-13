"""Prueba de generalización de la ficha (rally.generalizacion) para modelos exportados a numpy.

La etapa `generalizacion` evalúa `models/ppo`. Este script corre exactamente las mismas pruebas de
params.yaml (mismas semillas, mismo ruido de sensores, mismas referencias) con cualquier `.npz` de
agentes/red_numpy.py, para comparar modelos que no están en `models/ppo`. El promedio es el de
`rally seleccionar`: la media de vueltas de las pruebas con referencia.

Uso:
  python scripts/analisis/generalizacion_modelos.py --modelo v6=RUTA.npz --modelo control=RUTA.npz \\
      [--pruebas diluvio,limite_lluvia] [--salida metrics/generalizacion-modelos.json]
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from rally import track
from rally.agentes.red_numpy import RedNumpy
from rally.env import AutonomousRallyEnv
from rally.pipeline import _metricas


def _lote(args):
    """Igual que generalizacion._lote, con el piloto cargado desde un .npz."""
    ruta, ambiente, prueba, semillas = args
    env = AutonomousRallyEnv(**{**ambiente, **prueba.get("ambiente", {})})
    ruido = prueba.get("ruido_sensores", 0.0)
    red = RedNumpy(ruta)
    out = []
    for s in semillas:
        rng = np.random.default_rng(s)
        obs, info = env.reset(seed=s)
        total, done = 0.0, False
        while not done:
            if ruido:
                obs = (obs + rng.normal(0.0, ruido, obs.shape)).astype(np.float32)
            obs, r, term, trunc, info = env.step(red(obs))
            total += r
            done = term or trunc
        out.append({"ok": info["outcome"] == "exito", "t": info["t"], "r": total,
                    "inc": info["off_track_events"] + (info["outcome"] == "choque"),
                    "prog": info["s_best"] / track.largo(info)})
    return ruta, prueba["nombre"], out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", action="append", required=True, metavar="NOMBRE=RUTA.npz")
    ap.add_argument("--pruebas", help="solo estas pruebas (además de seco y mojado)")
    ap.add_argument("--salida", default="metrics/generalizacion-modelos.json")
    a = ap.parse_args(argv)
    modelos = dict(m.split("=", 1) for m in a.modelo)
    p = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))
    amb, pg, pe = p["ambiente"], p["generalizacion"], p["evaluacion"]
    semillas = list(range(pg["semilla_inicial"], pg["semilla_inicial"] + pg["episodios"]))
    elegidas = set(a.pruebas.split(",")) if a.pruebas else None
    extra = [pr for pr in pg["pruebas"] if elegidas is None or pr["nombre"] in elegidas]
    pruebas = [{"nombre": "seco", "ambiente": {"mu": pe["mu_seco"]}},
               {"nombre": "mojado", "ambiente": {"mu": pe["mu_mojado"]}}] + extra
    tareas = [(ruta, amb, pr, semillas[i:i + 10]) for ruta in modelos.values() for pr in pruebas
              for i in range(0, len(semillas), 10)]
    filas = {}
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        for ruta, nombre, out in ex.map(_lote, tareas):
            filas.setdefault((ruta, nombre), []).extend(out)
    res, resumen = {}, {}
    for nombre, ruta in modelos.items():
        res[nombre] = {pr["nombre"]: _metricas(filas[(ruta, pr["nombre"])]) for pr in pruebas}
        calificadas = [pr["nombre"] for pr in extra if pr.get("referencia")]
        prom = sum(res[nombre][n]["vueltas_pct"] for n in calificadas) / len(calificadas)
        peor = min(calificadas, key=lambda n: res[nombre][n]["vueltas_pct"])
        resumen[nombre] = {"promedio_pruebas_pct": round(prom, 1), "pruebas": len(calificadas),
                           "peor": peor, "peor_pct": res[nombre][peor]["vueltas_pct"]}
    salida = {"semillas": [semillas[0], semillas[-1]], "modelos": modelos, "resumen": resumen, "resultados": res}
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    nombres = [pr["nombre"] for pr in pruebas]
    for nombre in modelos:
        print(nombre, resumen[nombre])
        print("   " + "  ".join(f"{n}={res[nombre][n]['vueltas_pct']:.0f}" for n in nombres))


if __name__ == "__main__":
    main()
