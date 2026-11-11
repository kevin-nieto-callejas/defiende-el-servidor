"""Otra semilla del experimento v6: el PPO de params.yaml con las pistas y la semilla indicadas.

La v6 y su control se entrenaron con la semilla 0. La v5 y la v5-s1 mostraron que la semilla puede
cambiar el resultado en una pista nueva, así que esto repite los dos con otra semilla, en el mismo
computador y con el mismo código. Se evalúan después en las pistas de la fase A, nunca en la Sierra
(la prueba reservada ya se corrió una vez).

Uso:
  python scripts/analisis/entrenar_semilla.py --pistas monaco,bosque,puerto --semilla 1   → models/semillas-v6/v6-s1
  python scripts/analisis/entrenar_semilla.py --pistas monaco --semilla 1                 → models/semillas-v6/control-s1
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from rally import track
from rally.agentes import ppo
from rally.env import VERSION
from rally.pipeline import DEMOS, _config_ambiente, _evaluador_rapido, _run, params


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pistas", required=True)
    ap.add_argument("--semilla", type=int, required=True)
    a = ap.parse_args(argv)
    pistas = track.validar_entrenamiento(a.pistas.split(","))
    nombre = f"{'control' if pistas == ['monaco'] else 'v6'}-s{a.semilla}"
    salida = Path("models/semillas-v6") / nombre
    p = params()
    amb = p["ambiente"]
    pc = {**p["ppo"], "pistas": pistas, "semilla": a.semilla}
    t0 = time.time()
    with _run(f"ppo-{nombre}", pc, {"algoritmo": "PPO", "hipotesis": pc["hipotesis"], "contraste": "semillas-v6",
                                    "pistas_entrenamiento": ",".join(pistas)}) as run:
        huella = hashlib.sha1(json.dumps([amb, pc, VERSION, _config_ambiente()[1]], sort_keys=True).encode()
                              + DEMOS.read_bytes()).hexdigest()[:16]
        _, n_ep = ppo.entrenar(amb, pc, DEMOS, salida, None, _evaluador_rapido(amb, p["evaluacion"], pistas=pistas),
                               ppo.PuntoGuardado(f"runs/semillas-v6/{nombre}", huella))
        info = json.loads((salida / "info.json").read_text(encoding="utf-8"))
        info.update({"mlflow_run_id": run.info.run_id, "ambiente_version": VERSION,
                     "ambiente_huella": _config_ambiente()[1], "pistas_entrenamiento": pistas,
                     "semilla": a.semilla, "segundos": round(time.time() - t0, 1)})
        (salida / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Listo: {salida} ({n_ep} episodios)")


if __name__ == "__main__":
    main()
