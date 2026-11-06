"""Control del experimento v6: el mismo PPO de params.yaml, pero entrenado solo en Mónaco.

La v6 cambia una sola cosa frente a este control: las pistas de entrenamiento. Los dos se
entrenan en el mismo computador, con el mismo código, la misma semilla y los mismos
hiperparámetros, así que la diferencia entre ellos se debe a las pistas y no a la plataforma
(los modelos v5 se entrenaron en otro equipo, con otras versiones de PyTorch y numpy).

Uso:  python scripts/analisis/control_monaco.py      → models/control-ppo-monaco/modelo.zip
"""
import hashlib
import json
import time
from pathlib import Path

from rally.agentes import ppo
from rally.env import VERSION
from rally.pipeline import DEMOS, _config_ambiente, _evaluador_rapido, _run, params

SALIDA = Path("models/control-ppo-monaco")


def main():
    p = params()
    amb = p["ambiente"]
    pc = {**p["ppo"], "pistas": ["monaco"],
          "hipotesis": "Control de la v6: misma configuración, solo Mónaco"}
    t0 = time.time()
    with _run("ppo-control-monaco", pc, {"algoritmo": "PPO", "hipotesis": pc["hipotesis"],
                                         "contraste": "control-v6", "pistas_entrenamiento": "monaco"}) as run:
        huella = hashlib.sha1(json.dumps([amb, pc, VERSION, _config_ambiente()[1]], sort_keys=True).encode()
                              + DEMOS.read_bytes()).hexdigest()[:16]
        _, n_ep = ppo.entrenar(amb, pc, DEMOS, SALIDA, None,
                               _evaluador_rapido(amb, p["evaluacion"], pistas=["monaco"]),
                               ppo.PuntoGuardado("runs/control-ppo-monaco", huella))
        info = json.loads((SALIDA / "info.json").read_text(encoding="utf-8"))
        info.update({"mlflow_run_id": run.info.run_id, "ambiente_version": VERSION,
                     "ambiente_huella": _config_ambiente()[1], "pistas_entrenamiento": ["monaco"],
                     "segundos": round(time.time() - t0, 1)})
        (SALIDA / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Control listo: {SALIDA} ({n_ep} episodios)")


if __name__ == "__main__":
    main()
