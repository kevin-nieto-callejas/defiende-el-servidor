"""Cierra los runs que el apagón por calor dejó abiertos; se conservan como interrumpidos."""
import warnings

warnings.filterwarnings("ignore")
from mlflow import MlflowClient

from rally.agentes.seguimiento import EXPERIMENTO, TRACKING_URI

c = MlflowClient(tracking_uri=TRACKING_URI)
exp = c.get_experiment_by_name(EXPERIMENTO)
for r in c.search_runs([exp.experiment_id], "attributes.status = 'RUNNING'", max_results=20):
    c.set_tag(r.info.run_id, "diagnostico", "Interrumpido: el PC se apagó por calor el 2026-11-01 a las 19:50")
    c.set_terminated(r.info.run_id, status="KILLED")
    print("interrumpido:", r.info.run_name, r.info.run_id[:8])
