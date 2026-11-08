"""Resultados de un modelo con la suite de la ficha, en el formato de los manifiestos.

Mismo protocolo y mismas métricas que la etapa `evaluar` (pipeline._metricas): 100 semillas desde
la 0, seco μ = 0.9 y lluvia μ = 0.5, ambiente base, en Mónaco. Sirve para modelos que no salen de
`dvc repro` completo (la etapa `evaluar` también necesita la tabla Q).

Con el .npz (exportación a numpy de agentes/red_numpy.py) corre mucho más rápido que con PyTorch en
varios procesos, y es el mismo motor que sirve la API.

Uso:  python scripts/analisis/evaluar_ficha.py RUTA/modelo.{zip,npz} --salida metrics/v6-ficha.json
"""
import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

from rally import track
from rally.env import AutonomousRallyEnv
from rally.pipeline import _metricas


def _piloto(ruta):
    if str(ruta).endswith(".npz"):
        from rally.agentes.red_numpy import RedNumpy
        red = RedNumpy(ruta)
        return lambda obs, info: red(obs)
    from rally.agentes.ppo import PilotoPPO
    return PilotoPPO(ruta)


def lote(args):
    ruta, ambiente, mu, semillas = args
    env = AutonomousRallyEnv(**{**ambiente, "mu": mu})
    pol = _piloto(ruta)
    out = []
    for s in semillas:
        obs, info = env.reset(seed=s)
        total, done = 0.0, False
        while not done:
            obs, r, term, trunc, info = env.step(pol(obs, info))
            total += r
            done = term or trunc
        out.append({"ok": info["outcome"] == "exito", "t": info["t"], "r": total,
                    "inc": info["off_track_events"] + (info["outcome"] == "choque"),
                    "prog": info["s_best"] / track.largo(info)})
    return mu, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelo")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    p = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))
    pe = p["evaluacion"]
    semillas = list(range(pe["semilla_inicial"], pe["semilla_inicial"] + pe["episodios"]))
    cond = {"seco": pe["mu_seco"], "mojado": pe["mu_mojado"]}
    trabajos = [(a.modelo, p["ambiente"], mu, semillas[i:i + 25]) for mu in cond.values()
                for i in range(0, len(semillas), 25)]
    filas = {}
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        for mu, out in ex.map(lote, trabajos):
            filas.setdefault(mu, []).extend(out)
    res = {nombre: _metricas(filas[mu]) for nombre, mu in cond.items()}
    sha = hashlib.sha256(Path(a.modelo).read_bytes()).hexdigest()
    motor = {"motor": "pytorch", "model_sha256": sha}
    if a.modelo.endswith(".npz"):
        import numpy as np
        with np.load(a.modelo, allow_pickle=False) as z:   # exportación verificada contra PyTorch
            motor = {"motor": "numpy", "model_sha256": str(z["fuente_sha256"]), "npz_sha256": sha,
                     "max_diferencia_con_pytorch": float(z["max_diferencia"])}
    salida = {"modelo": a.modelo, **motor,
              "suite": "ficha-100-semillas-0-99", "pista": "monaco", "resultados": res}
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
