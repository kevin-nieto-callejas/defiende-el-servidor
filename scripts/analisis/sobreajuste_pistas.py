"""¿El agente aprendió a manejar o memorizó sus pistas? Lo evalúa en pistas que nunca vio.

Mismo protocolo de la ficha (100 semillas desde la 0, seco μ = 0.9 y lluvia μ = 0.5, ambiente
base de params.yaml) en todas las pistas:

  monaco, bosque, puerto   pistas que un modelo puede haber usado para entrenar
  sierra                   pista reservada: ningún modelo entrena en ella (track.RESERVADAS)
  puerto_r95               control: el Puerto con ninguna curva más cerrada que la de Mónaco
                           (9.5 m). Separa "no conoce el trazado" de "la curva es más cerrada
                           de lo que distingue su sensor de curvatura"

El experto y el maestro sirven de control: si ellos completan una pista y el agente no, el
problema es del agente, no del trazado.

Cada modelo es el .zip de PyTorch o su exportación a numpy (.npz) que sirve la API de Vercel
(web/api/_paquete/pesos/<sha256>.npz); la exportación se comparó con PyTorch al crearse.

Uso:
  python scripts/analisis/sobreajuste_pistas.py \\
      --modelo ppo-modelo-v5=RUTA.npz:monaco \\
      --modelo ppo-modelo-v6-pistas=models/ppo/modelo.zip:monaco,bosque,puerto \\
      [--episodios 100] [--salida metrics/sobreajuste-pistas.json]

Después de los dos puntos van las pistas con las que se entrenó cada modelo.
"""
import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from rally import policies, track
from rally.env import VERSION, AutonomousRallyEnv

# Control: se registra al importar para que también exista en los procesos de evaluación.
PUERTO_R95 = track.registrar(track.Pista(
    "puerto_r95", [(n, x, y, max(r, track.MONACO.R)) for n, x, y, r in track.PUERTO.VERTICES],
    track.PUERTO.GATE_CORNERS, descripcion="Control: el Puerto sin curvas más cerradas que Mónaco"))

PISTAS = ["monaco", "bosque", "puerto", "sierra", "puerto_r95"]
REFERENCIAS = ["experto", "maestro"]


def _piloto(nombre, ruta, semilla):
    if ruta is None:
        return policies.crear(nombre, semilla)
    if str(ruta).endswith(".npz"):
        from rally.agentes.red_numpy import RedNumpy
        red = RedNumpy(ruta)
        return lambda obs, info: red(obs)
    from rally.agentes.ppo import PilotoPPO
    return PilotoPPO(ruta)


def medir(args):
    nombre, ruta, pista, mu, semillas, ambiente = args
    env = AutonomousRallyEnv(**{**ambiente, "mu": mu}, pista=pista)
    fijo = _piloto(nombre, ruta, semillas[0]) if ruta else None
    out = []
    for s in semillas:
        pol = fijo or _piloto(nombre, None, s)
        obs, info = env.reset(seed=s)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        out.append({"semilla": s, "resultado": info["outcome"], "t": info["t"],
                    "progreso": max(info["s_best"], 0) / track.largo(info),
                    "puerta": info["next_cp"], "salidas": info["off_track_events"]})
    return nombre, pista, mu, out


def resumir(casos, pista):
    tiempos = [c["t"] for c in casos if c["resultado"] == "exito"]
    fallos, puertas = {}, {}
    nombres = track.obtener(pista).GATE_NAMES
    for c in casos:
        if c["resultado"] != "exito":
            fallos[c["resultado"]] = fallos.get(c["resultado"], 0) + 1
            donde = nombres[min(c["puerta"], len(nombres)) - 1]
            puertas[donde] = puertas.get(donde, 0) + 1
    return {"vueltas_pct": round(100 * len(tiempos) / len(casos), 1),
            "tiempo_mediano_s": round(float(np.median(tiempos)), 1) if tiempos else None,
            "progreso_medio_pct": round(100 * float(np.mean([c["progreso"] for c in casos])), 1),
            "fallos_por_causa": fallos, "fallos_antes_de": puertas}


def _identidad(ruta, pistas):
    sha = hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    ident = {"archivo": str(ruta), "motor": "pytorch", "model_sha256": sha}
    if str(ruta).endswith(".npz"):
        with np.load(ruta, allow_pickle=False) as z:
            ident = {"archivo": str(ruta), "motor": "numpy", "model_sha256": str(z["fuente_sha256"]),
                     "npz_sha256": sha, "max_diferencia_con_pytorch": float(z["max_diferencia"])}
    return {**ident, "pistas_entrenamiento": pistas}


def _modelo(texto):
    nombre, resto = texto.split("=", 1)
    ruta, _, pistas = resto.rpartition(":") if ":" in resto else (resto, "", "monaco")
    pistas = track.validar_entrenamiento(pistas.split(","))
    if not Path(ruta).exists():
        raise argparse.ArgumentTypeError(f"No existe {ruta}")
    return nombre, ruta, pistas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", type=_modelo, action="append", required=True, metavar="NOMBRE=RUTA:PISTAS")
    ap.add_argument("--episodios", type=int, default=100)
    ap.add_argument("--salida", default="metrics/sobreajuste-pistas.json")
    a = ap.parse_args(argv)

    p = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))
    ambiente, pe = p["ambiente"], p["evaluacion"]
    semillas = list(range(pe["semilla_inicial"], pe["semilla_inicial"] + a.episodios))
    condiciones = {"seco": pe["mu_seco"], "mojado": pe["mu_mojado"]}
    lotes = [semillas[i:i + 25] for i in range(0, len(semillas), 25)]
    pilotos = [(n, None) for n in REFERENCIAS] + [(n, r) for n, r, _ in a.modelo]
    trabajos = [(n, r, pista, mu, lote, ambiente)
                for n, r in pilotos for pista in PISTAS for mu in condiciones.values() for lote in lotes]

    t0 = time.time()
    casos = {}
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        for nombre, pista, mu, out in ex.map(medir, trabajos):
            casos.setdefault((nombre, pista, mu), []).extend(out)

    resultados = {n: {pista: {cond: resumir(sorted(casos[(n, pista, mu)], key=lambda c: c["semilla"]), pista)
                              for cond, mu in condiciones.items()} for pista in PISTAS} for n, _ in pilotos}
    salida = {
        "pregunta": "¿Los modelos manejan en pistas que nunca vieron al entrenar?",
        "ambiente_version": VERSION,
        "protocolo": {"episodios": a.episodios, "semillas": [semillas[0], semillas[-1]],
                      "condiciones": condiciones, "ambiente": ambiente},
        "pistas": {n: {"largo_m": round(track.obtener(n).LAP, 1), "curvas": len(track.obtener(n).VERTICES),
                       "radio_min_m": track.obtener(n).R, "sentido": track.obtener(n).sentido,
                       "reservada": n in track.RESERVADAS, "descripcion": track.obtener(n).descripcion}
                   for n in PISTAS},
        "modelos": {n: _identidad(r, pistas) for n, r, pistas in a.modelo},
        "resultados": resultados,
        "segundos": round(time.time() - t0, 1),
    }
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{'piloto':26s} {'pista':11s} {'seco':>16s} {'lluvia':>16s}")
    for nombre, por_pista in resultados.items():
        for pista, r in por_pista.items():
            fila = [f"{r[c]['vueltas_pct']:5.1f} % {r[c]['tiempo_mediano_s'] or '-':>6} s" for c in condiciones]
            print(f"{nombre:26s} {pista:11s} {fila[0]:>16s} {fila[1]:>16s}")
    print(f"-> {a.salida} ({salida['segundos']} s)")


if __name__ == "__main__":
    main()
