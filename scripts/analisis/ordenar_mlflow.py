"""Ordena el historial: runs cortados por apagones e hipótesis escritas después del hecho."""
import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
from mlflow import MlflowClient

from rally.agentes.seguimiento import EXPERIMENTO, TRACKING_URI

c = MlflowClient(tracking_uri=TRACKING_URI)
exp = c.get_experiment_by_name(EXPERIMENTO)
hoy = time.time() * 1000 - 6 * 3600 * 1000
for r in c.search_runs([exp.experiment_id], "attributes.status = 'RUNNING'", max_results=100):
    if r.info.start_time > hoy:       # el entrenamiento de ahora no se toca
        print("sigue vivo:", r.info.run_name, r.info.run_id[:8])
        continue
    c.set_tag(r.info.run_id, "diagnostico", "Interrumpido: el PC se apagó; el run siguiente reanudó desde el punto de guardado")
    c.set_tag(r.info.run_id, "checkpoint", "sin checkpoint disponible en este run")
    c.set_terminated(r.info.run_id, status="KILLED", end_time=r.info.start_time)
    print("interrumpido:", r.info.run_name, r.info.run_id[:8])

for f in sorted(Path("manifests").glob("*.json")):
    m = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or not m.get("run_id"):
        print("sin run_id:", f.name)
        continue
    try:
        c.get_run(m["run_id"])
    except Exception:
        print("run no está en este MLflow:", f.name)
        continue
    c.set_tag(m["run_id"], "hipotesis", m["hipotesis"] or "sin registrar")
    c.set_tag(m["run_id"], "hipotesis_registrada_despues", "true")
    c.set_tag(m["run_id"], "decision", m["decision"] or "sin decidir")
    c.set_tag(m["run_id"], "level_id", m["level_id"] or "-")
    print("hipótesis:", f.stem, m["run_id"][:8])
